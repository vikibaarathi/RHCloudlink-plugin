"""
CloudLink Registration Blueprint
Serves the in-timer event registration UI at /cloudlink/setup.

Flow (mirrors the Angular registration form exactly):
  1. POST /register           -> get eventid + privatekey
  2. POST /uploads/presign    -> get uploadUrl + publicUrl
  3. PUT  {uploadUrl}         -> upload image bytes direct to S3 (no auth needed)
  4. PATCH /event/{id}        -> save eventlogourl (X-Private-Key header)
  5. Save eventid + privatekey to RH options

CORS note: The CloudLink API uses Access-Control-Allow-Origin: *
and S3 bucket CORS also allows all origins -- so timer machines
without a domain/IP address can call these endpoints freely.
"""

import os
import logging
import requests
from flask import Blueprint, render_template, request, jsonify
from .constants import ALLOWED_IMAGE_TYPES, OPT_EVENT_ID, OPT_EVENT_KEY

logger = logging.getLogger(__name__)


def _upload_image(api_client, event_id, priv_key, image_file):
    """Shared image upload flow: presign -> S3 PUT -> PATCH event.
    Returns the public URL on success, or None on failure.
    """
    content_type = image_file.content_type or 'image/jpeg'

    if content_type not in ALLOWED_IMAGE_TYPES:
        logger.warning(f'[CloudLink] Unsupported image type {content_type} -- skipping upload')
        return None

    file_bytes = image_file.read()
    file_name = image_file.filename or 'image.jpg'

    # Step 1: Get presigned URL
    presign_data = api_client.presign_upload(file_name, content_type)
    if presign_data is None:
        logger.warning('[CloudLink] Presign failed -- no image uploaded')
        return None

    upload_url = presign_data.get('uploadUrl')
    public_url = presign_data.get('publicUrl')

    if not upload_url or not public_url:
        logger.warning('[CloudLink] Missing uploadUrl/publicUrl in presign response')
        return None

    # Step 2: PUT image to S3
    if not api_client.upload_to_s3(upload_url, file_bytes, content_type):
        logger.warning('[CloudLink] S3 upload failed -- event created, no image')
        return None

    # Step 3: PATCH event with image URL
    if not api_client.patch_event(event_id, priv_key, {'eventlogourl': public_url}):
        logger.warning('[CloudLink] Event update failed -- event created, image not saved')
        return None

    logger.info(f'[CloudLink] Image uploaded for {event_id}: {public_url}')
    return public_url


def create_registration_blueprint(rhapi, api_client=None):
    """
    Factory -- creates and returns the Flask Blueprint.
    Pass rhapi so the blueprint can read/write RH options.
    Pass api_client for HTTP communication with CloudLink API.
    """

    bp = Blueprint(
        'cloudlink_registration',
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
        url_prefix='/cloudlink'
    )

    # ──────────────────────────────────────────────────────────────────────────
    # GET /cloudlink/setup -- render the registration page
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/setup')
    def setup():
        eventid  = rhapi.db.option(OPT_EVENT_ID)  or ''
        eventkey = rhapi.db.option(OPT_EVENT_KEY) or ''
        return render_template('cloudlink/setup.html',
                               eventid=eventid,
                               eventkey=eventkey)

    # ──────────────────────────────────────────────────────────────────────────
    # POST /cloudlink/register -- full registration flow
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

            reg_data = api_client.register_event(reg_payload)

            if reg_data is None:
                return jsonify({'success': False, 'error': 'Registration failed -- cannot reach CloudLink API'}), 502

            event_id = reg_data.get('eventid')
            priv_key = reg_data.get('privatekey')

            if not event_id or not priv_key:
                logger.error(f'[CloudLink] Missing keys in registration response: {reg_data}')
                return jsonify({'success': False, 'error': 'Invalid response from CloudLink API'}), 502

            logger.info(f'[CloudLink] Event registered: {event_id}')

            # ── Step 2 + 3 + 4: Image upload (if file provided) ────────────
            image_file = request.files.get('image_file') if has_image else None
            if image_file and image_file.filename:
                _upload_image(api_client, event_id, priv_key, image_file)

            # ── Step 5: Save keys to RH ─────────────────────────────────────
            rhapi.db.option_set(OPT_EVENT_ID,  event_id)
            rhapi.db.option_set(OPT_EVENT_KEY, priv_key)
            logger.info(f'[CloudLink] Keys saved to RH for event {event_id}')

            return jsonify({'success': True, 'eventid': event_id, 'privatekey': priv_key})

        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'error': 'Cannot reach CloudLink API -- check internet connection'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'CloudLink API timed out -- please try again'}), 504
        except Exception as e:
            logger.error(f'[CloudLink] Registration error: {e}', exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ──────────────────────────────────────────────────────────────────────────
    # GET /cloudlink/event-details -- proxy to fetch event details from API
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/event-details', methods=['GET'])
    def event_details():
        try:
            event_id = request.args.get('eventid', '').strip()
            if not event_id:
                return jsonify({'success': False, 'error': 'eventid required'}), 400

            data = api_client.get_event_details(event_id)
            if data is None:
                return jsonify({'success': False, 'error': 'Cannot reach CloudLink API'}), 502

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
    # POST /cloudlink/upload-logo -- upload/replace logo for an existing event
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

            # Check file size before uploading
            file_bytes = image_file.read()
            if len(file_bytes) > 5 * 1024 * 1024:
                return jsonify({'success': False, 'error': 'Image must be under 5MB'}), 400
            # Reset stream so _upload_image can re-read
            image_file.seek(0)

            public_url = _upload_image(api_client, event_id, priv_key, image_file)
            if public_url is None:
                return jsonify({'success': False, 'error': 'Image upload failed'}), 502

            return jsonify({'success': True, 'logourl': public_url})

        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'error': 'Cannot reach CloudLink API -- check internet connection'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'CloudLink API timed out -- please try again'}), 504
        except Exception as e:
            logger.error(f'[CloudLink] Upload logo error: {e}', exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    # ──────────────────────────────────────────────────────────────────────────
    # POST /cloudlink/clear -- reset saved keys
    # ──────────────────────────────────────────────────────────────────────────
    @bp.route('/clear', methods=['POST'])
    def clear():
        rhapi.db.option_set(OPT_EVENT_ID,  '')
        rhapi.db.option_set(OPT_EVENT_KEY, '')
        logger.info('[CloudLink] Keys cleared')
        return jsonify({'success': True})

    return bp
