"""
CloudLink Registration Blueprint
Serves the in-timer event registration UI at /cloudlink/setup.

Flow (mirrors the Angular registration form exactly):
  1. POST /register           → get eventid + privatekey
  2. POST /uploads/presign    → get uploadUrl + publicUrl
  3. PUT  {uploadUrl}         → upload image bytes direct to S3 (no auth needed)
  4. PATCH /event/{id}        → save eventlogourl (X-Private-Key header)
  5. Save eventid + privatekey to RH options

CORS note: The CloudLink API uses Access-Control-Allow-Origin: *
and S3 bucket CORS also allows all origins — so timer machines
without a domain/IP address can call these endpoints freely.
"""

import os
import logging
import requests
from flask import Blueprint, render_template, request, jsonify

logger = logging.getLogger(__name__)

API_TIMEOUT_SHORT = 10   # seconds — for API calls
API_TIMEOUT_S3    = 30   # seconds — for S3 PUT (file upload)

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


def create_registration_blueprint(rhapi):
    """
    Factory — creates and returns the Flask Blueprint.
    Pass rhapi so the blueprint can read/write RH options.
    """

    try:
        from .config import CL_API_ENDPOINT
    except ImportError:
        CL_API_ENDPOINT = 'https://api.rhcloudlink.com'

    bp = Blueprint(
        'cloudlink_registration',
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
        url_prefix='/cloudlink'
    )

    # ──────────────────────────────────────────────────────────────────────────
    # GET /cloudlink/setup — render the registration page
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/setup')
    def setup():
        eventid  = rhapi.db.option('cl-event-id')  or ''
        eventkey = rhapi.db.option('cl-event-key') or ''
        return render_template('cloudlink/setup.html',
                               eventid=eventid,
                               eventkey=eventkey)

    # ──────────────────────────────────────────────────────────────────────────
    # POST /cloudlink/register — full registration flow
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/register', methods=['POST'])
    def register():
        try:
            # ── Read form fields ────────────────────────────────────────────
            event_name     = (request.form.get('eventname',    '') or '').strip()
            email_id       = (request.form.get('emailid',      '') or '').strip()
            event_date     = (request.form.get('eventdate',    '') or '').strip()
            event_end_date = (request.form.get('eventenddate', '') or '').strip() or event_date
            event_city     = (request.form.get('eventcity',    '') or '').strip()
            event_country  = (request.form.get('eventcountry', '') or '').strip()
            event_desc     = (request.form.get('eventdesc',    '') or '').strip()
            event_public   = (request.form.get('eventpublic',  'private') or 'private').strip()
            has_image      = request.form.get('has_image', 'false') == 'true'

            if event_public not in ('public', 'private'):
                event_public = 'private'

            if not event_name:
                return jsonify({'success': False, 'error': 'Event name is required'}), 400
            if not email_id:
                return jsonify({'success': False, 'error': 'Email address is required'}), 400

            # ── Step 1: Register the event ──────────────────────────────────
            reg_payload = {
                'emailid':      email_id,
                'eventname':    event_name,
                'eventdate':    event_date,
                'eventenddate': event_end_date,
                'eventcity':    event_city,
                'eventcountry': event_country,
                'eventdesc':    event_desc,
                'eventpublic':  event_public,
                'eventtype':    'T',
            }

            reg_resp = requests.post(
                f'{CL_API_ENDPOINT}/register',
                json=reg_payload,
                timeout=API_TIMEOUT_SHORT
            )

            if reg_resp.status_code != 200:
                logger.error(f'[CloudLink] Registration failed: {reg_resp.status_code} {reg_resp.text}')
                return jsonify({'success': False, 'error': f'Registration failed ({reg_resp.status_code})'}), 502

            reg_data  = reg_resp.json()
            event_id  = reg_data.get('eventid')
            priv_key  = reg_data.get('privatekey')

            if not event_id or not priv_key:
                logger.error(f'[CloudLink] Missing keys in registration response: {reg_data}')
                return jsonify({'success': False, 'error': 'Invalid response from CloudLink API'}), 502

            logger.info(f'[CloudLink] Event registered: {event_id}')

            # ── Step 2 + 3 + 4: Image upload (if file provided) ────────────
            # Mirrors Angular: presign → PUT to S3 → PATCH event
            image_file = request.files.get('image_file') if has_image else None

            if image_file and image_file.filename:
                content_type = image_file.content_type or 'image/jpeg'

                if content_type not in ALLOWED_IMAGE_TYPES:
                    logger.warning(f'[CloudLink] Unsupported image type {content_type} — skipping upload')
                else:
                    file_bytes = image_file.read()
                    file_name  = image_file.filename or 'image.jpg'

                    # Step 2: Get presigned URL
                    presign_resp = requests.post(
                        f'{CL_API_ENDPOINT}/uploads/presign',
                        json={'fileName': file_name, 'contentType': content_type},
                        timeout=API_TIMEOUT_SHORT
                    )

                    if presign_resp.status_code == 200:
                        presign_data = presign_resp.json().get('data', {})
                        upload_url   = presign_data.get('uploadUrl')
                        public_url   = presign_data.get('publicUrl')

                        if upload_url and public_url:
                            # Step 3: PUT image direct to S3
                            s3_resp = requests.put(
                                upload_url,
                                data=file_bytes,
                                headers={'Content-Type': content_type},
                                timeout=API_TIMEOUT_S3
                            )

                            if s3_resp.status_code in (200, 204):
                                # Step 4: PATCH event with image URL
                                patch_resp = requests.patch(
                                    f'{CL_API_ENDPOINT}/event/{event_id}',
                                    json={'eventlogourl': public_url},
                                    headers={'X-Private-Key': priv_key},
                                    timeout=API_TIMEOUT_SHORT
                                )
                                if patch_resp.status_code == 200:
                                    logger.info(f'[CloudLink] Image uploaded for {event_id}: {public_url}')
                                else:
                                    logger.warning(f'[CloudLink] Update failed ({patch_resp.status_code}) — event created, image not saved')
                            else:
                                logger.warning(f'[CloudLink] Cloud storage save failed ({s3_resp.status_code}) — event created, no image')
                        else:
                            logger.warning('[CloudLink] Missing uploadUrl/publicUrl in presign response')
                    else:
                        logger.warning(f'[CloudLink] Presign failed ({presign_resp.status_code}) — event created, no image')

            # ── Step 5: Save keys to RH ─────────────────────────────────────
            rhapi.db.option_set('cl-event-id',  event_id)
            rhapi.db.option_set('cl-event-key', priv_key)
            logger.info(f'[CloudLink] Keys saved to RH for event {event_id}')

            return jsonify({'success': True, 'eventid': event_id, 'privatekey': priv_key})

        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'error': 'Cannot reach CloudLink API — check internet connection'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'CloudLink API timed out — please try again'}), 504
        except Exception as e:
            logger.error(f'[CloudLink] Registration error: {e}', exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ──────────────────────────────────────────────────────────────────────────
    # GET /cloudlink/event-details — proxy to fetch event details from API
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/event-details', methods=['GET'])
    def event_details():
        try:
            event_id = request.args.get('eventid', '').strip()
            if not event_id:
                return jsonify({'success': False, 'error': 'eventid required'}), 400

            resp = requests.get(
                f'{CL_API_ENDPOINT}/event',
                params={'eventid': event_id},
                timeout=API_TIMEOUT_SHORT
            )
            if resp.status_code != 200:
                return jsonify({'success': False, 'error': f'API error ({resp.status_code})'}), 502

            data = resp.json()
            logger.info(f'[CloudLink] event-details raw response type={type(data).__name__}: {str(data)[:200]}')

            # API returns a list of items, or a string error message
            event = None
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('sk', '').startswith('event'):
                        event = item
                        break
                if not event and data:
                    # fallback: take first dict item
                    event = next((i for i in data if isinstance(i, dict)), None)

            if not event:
                return jsonify({'success': False, 'error': 'Event not found'}), 404

            return jsonify({'success': True, 'event': event})

        except Exception as e:
            logger.error(f'[CloudLink] Event details error: {e}', exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ──────────────────────────────────────────────────────────────────────────
    # POST /cloudlink/upload-logo — upload/replace logo for an existing event
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/upload-logo', methods=['POST'])
    def upload_logo():
        try:
            event_id = (request.form.get('eventid',  '') or '').strip()
            priv_key = (request.form.get('eventkey', '') or '').strip()
            image_file = request.files.get('image_file')

            if not event_id or not priv_key:
                return jsonify({'success': False, 'error': 'Event ID and private key are required'}), 400
            if not image_file or not image_file.filename:
                return jsonify({'success': False, 'error': 'No image file provided'}), 400

            content_type = image_file.content_type or 'image/jpeg'
            if content_type not in ALLOWED_IMAGE_TYPES:
                return jsonify({'success': False, 'error': 'Only JPEG, PNG or WebP images are allowed'}), 400

            file_bytes = image_file.read()
            if len(file_bytes) > 5 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Image must be under 5MB'}), 400

            file_name = image_file.filename or 'image.jpg'

            # Step 1: Get presigned URL
            presign_resp = requests.post(
                f'{CL_API_ENDPOINT}/uploads/presign',
                json={'fileName': file_name, 'contentType': content_type},
                timeout=API_TIMEOUT_SHORT
            )
            if presign_resp.status_code != 200:
                return jsonify({'success': False, 'error': f'Presign failed ({presign_resp.status_code})'}), 502

            presign_data = presign_resp.json().get('data', {})
            upload_url   = presign_data.get('uploadUrl')
            public_url   = presign_data.get('publicUrl')

            if not upload_url or not public_url:
                return jsonify({'success': False, 'error': 'Invalid presign response'}), 502

            # Step 2: PUT image to S3
            s3_resp = requests.put(
                upload_url,
                data=file_bytes,
                headers={'Content-Type': content_type},
                timeout=API_TIMEOUT_S3
            )
            if s3_resp.status_code not in (200, 204):
                return jsonify({'success': False, 'error': f'S3 upload failed ({s3_resp.status_code})'}), 502

            # Step 3: PATCH event with new logo URL
            patch_resp = requests.patch(
                f'{CL_API_ENDPOINT}/event/{event_id}',
                json={'eventlogourl': public_url},
                headers={'X-Private-Key': priv_key},
                timeout=API_TIMEOUT_SHORT
            )
            if patch_resp.status_code != 200:
                return jsonify({'success': False, 'error': f'Event update failed ({patch_resp.status_code})'}), 502

            logger.info(f'[CloudLink] Logo updated for event {event_id}: {public_url}')
            return jsonify({'success': True, 'logourl': public_url})

        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'error': 'Cannot reach CloudLink API — check internet connection'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'CloudLink API timed out — please try again'}), 504
        except Exception as e:
            logger.error(f'[CloudLink] Upload logo error: {e}', exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ──────────────────────────────────────────────────────────────────────────
    # POST /cloudlink/clear — reset saved keys
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/clear', methods=['POST'])
    def clear():
        rhapi.db.option_set('cl-event-id',  '')
        rhapi.db.option_set('cl-event-key', '')
        logger.info('[CloudLink] Keys cleared')
        return jsonify({'success': True})

    return bp
