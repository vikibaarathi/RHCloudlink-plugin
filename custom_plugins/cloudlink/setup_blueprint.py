import os
import logging
import requests
from flask import Blueprint, render_template, request, jsonify

logger = logging.getLogger(__name__)

# RH logo path — served statically by RotorHazard
RH_LOGO_URL = '/static/image/RotorHazard Logo.svg'


def create_blueprint(rhapi):
    """
    CloudLink Flask Blueprint — in-timer event registration UI.
    Wired to the real CloudLink API (Phase 2).
    """

    # Pull the configured API endpoint from the plugin's own config
    try:
        from .config import CL_API_ENDPOINT
    except ImportError:
        CL_API_ENDPOINT = 'https://api.rhcloudlink.com'

    bp = Blueprint(
        'cloudlink_setup',
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
        url_prefix='/cloudlink'
    )

    # ------------------------------------------------------------------
    # GET /cloudlink/setup  — render the registration form
    # ------------------------------------------------------------------
    @bp.route('/setup')
    def setup():
        eventid  = rhapi.db.option('cl-event-id') or ''
        eventkey = rhapi.db.option('cl-event-key') or ''
        return render_template('cloudlink/setup.html', eventid=eventid, eventkey=eventkey)

    # ------------------------------------------------------------------
    # POST /cloudlink/register  — real registration via CloudLink API
    # ------------------------------------------------------------------
    @bp.route('/register', methods=['POST'])
    def register():
        try:
            event_name    = request.form.get('eventname', '').strip()
            event_date    = request.form.get('eventdate', '').strip()
            event_city    = request.form.get('eventcity', '').strip()
            event_country = request.form.get('eventcountry', '').strip()
            event_desc    = request.form.get('eventdesc', '').strip()
            email_id      = request.form.get('emailid', '').strip()
            event_public  = request.form.get('eventpublic', 'private').strip()
            image_mode    = request.form.get('image_mode', 'rh_logo')
            image_url     = request.form.get('image_url', '').strip()

            if not event_name:
                return jsonify({'success': False, 'error': 'Event name is required'}), 400
            if not email_id:
                return jsonify({'success': False, 'error': 'Email address is required'}), 400

            # ── Step 1: Determine initial logo URL ──────────────────────
            # For URL mode we can pass it straight to /register.
            # For file/rh_logo we register first (gets default logo), then upload.
            initial_logo_url = None
            if image_mode == 'url' and image_url:
                initial_logo_url = image_url

            # ── Step 2: Register the event ──────────────────────────────
            payload = {
                'emailid':      email_id,
                'eventname':    event_name,
                'eventdate':    event_date,
                'eventcity':    event_city,
                'eventcountry': event_country,
                'eventdesc':    event_desc,
                'eventpublic':  event_public if event_public in ('public', 'private') else 'private',
            }
            if initial_logo_url:
                payload['eventlogourl'] = initial_logo_url

            reg_resp = requests.post(
                f'{CL_API_ENDPOINT}/register',
                json=payload,
                timeout=15
            )

            if reg_resp.status_code != 200:
                logger.error(f'[CloudLink] Registration failed: {reg_resp.status_code} {reg_resp.text}')
                return jsonify({'success': False, 'error': f'Registration failed: {reg_resp.status_code}'}), 502

            reg_data  = reg_resp.json()
            event_id  = reg_data.get('eventid') or reg_data.get('data', {}).get('eventid')
            priv_key  = reg_data.get('privatekey') or reg_data.get('data', {}).get('privatekey')

            if not event_id or not priv_key:
                return jsonify({'success': False, 'error': 'Invalid response from CloudLink API'}), 502

            # ── Step 3: Handle image upload (file or RH logo) ───────────
            final_logo_url = initial_logo_url  # already set for URL mode

            if image_mode in ('upload', 'rh_logo'):
                image_file = None
                content_type = 'image/svg+xml'

                if image_mode == 'upload':
                    image_file = request.files.get('image_file')
                    if image_file and image_file.filename:
                        content_type = image_file.content_type or 'image/jpeg'
                    else:
                        image_file = None  # skip upload if nothing selected

                elif image_mode == 'rh_logo':
                    # Read the RH logo SVG from the static files on disk
                    rh_logo_path = os.path.join(
                        os.path.dirname(__file__), '..', '..', '..', '..', 'src', 'server',
                        'static', 'image', 'RotorHazard Logo.svg'
                    )
                    rh_logo_path = os.path.normpath(rh_logo_path)
                    if os.path.exists(rh_logo_path):
                        with open(rh_logo_path, 'rb') as f:
                            image_file = f.read()
                        content_type = 'image/svg+xml'
                    else:
                        logger.warning('[CloudLink] RH logo file not found, skipping image upload')

                if image_file is not None:
                    # Get presigned URL
                    url_resp = requests.post(
                        f'{CL_API_ENDPOINT}/event/{event_id}/upload-url',
                        params={'content-type': content_type},
                        headers={'X-Private-Key': priv_key},
                        timeout=10
                    )

                    if url_resp.status_code == 200:
                        url_data    = url_resp.json()
                        upload_url  = url_data.get('uploadUrl') or url_data.get('data', {}).get('uploadUrl')
                        image_s3url = url_data.get('imageUrl')  or url_data.get('data', {}).get('imageUrl')

                        if upload_url:
                            # Upload directly to S3
                            file_data = image_file if isinstance(image_file, bytes) else image_file.read()
                            s3_resp = requests.put(
                                upload_url,
                                data=file_data,
                                headers={'Content-Type': content_type},
                                timeout=30
                            )
                            if s3_resp.status_code in (200, 204):
                                final_logo_url = image_s3url
                                # Patch the event with the final logo URL
                                requests.patch(
                                    f'{CL_API_ENDPOINT}/event/{event_id}',
                                    json={'eventlogourl': final_logo_url},
                                    headers={'X-Private-Key': priv_key},
                                    timeout=10
                                )
                                logger.info(f'[CloudLink] Image uploaded for {event_id}: {final_logo_url}')
                            else:
                                logger.warning(f'[CloudLink] S3 upload failed ({s3_resp.status_code}), continuing without image')
                    else:
                        logger.warning(f'[CloudLink] Could not get presigned URL ({url_resp.status_code}), continuing without image')

            # ── Step 4: Save keys to RH ─────────────────────────────────
            rhapi.db.set_option('cl-event-id', event_id)
            rhapi.db.set_option('cl-event-key', priv_key)

            logger.info(f'[CloudLink] Event registered: {event_id} for "{event_name}"')

            return jsonify({
                'success':    True,
                'eventid':    event_id,
                'privatekey': priv_key,
                'logourl':    final_logo_url,
            })

        except requests.exceptions.ConnectionError:
            return jsonify({'success': False, 'error': 'Cannot reach CloudLink API. Check internet connection.'}), 503
        except requests.exceptions.Timeout:
            return jsonify({'success': False, 'error': 'CloudLink API timed out. Please try again.'}), 504
        except Exception as e:
            logger.error(f'[CloudLink] Registration error: {e}')
            return jsonify({'success': False, 'error': str(e)}), 500

    # ------------------------------------------------------------------
    # POST /cloudlink/clear-keys  — reset keys (start over)
    # ------------------------------------------------------------------
    @bp.route('/clear-keys', methods=['POST'])
    def clear_keys():
        rhapi.db.set_option('cl-event-id', '')
        rhapi.db.set_option('cl-event-key', '')
        return jsonify({'success': True})

    return bp
