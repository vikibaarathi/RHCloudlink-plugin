import os
import random
import string
import logging
from flask import Blueprint, render_template, request, jsonify

logger = logging.getLogger(__name__)


def create_blueprint(rhapi):
    """
    Creates and returns the CloudLink Flask Blueprint.
    Handles the in-timer event registration UI and mock API.
    Phase 2: replace mock_register() with real CloudLink API calls.
    """
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
        eventid = rhapi.db.option('cl-event-id') or ''
        eventkey = rhapi.db.option('cl-event-key') or ''
        return render_template(
            'cloudlink/setup.html',
            eventid=eventid,
            eventkey=eventkey,
        )

    # ------------------------------------------------------------------
    # POST /cloudlink/register  — mock registration (Phase 1)
    # Phase 2: call CloudLink API, get real eventid + privatekey back
    # ------------------------------------------------------------------
    @bp.route('/register', methods=['POST'])
    def register():
        try:
            event_name    = request.form.get('eventname', '').strip()
            event_date    = request.form.get('eventdate', '').strip()
            event_city    = request.form.get('eventcity', '').strip()
            event_country = request.form.get('eventcountry', '').strip()
            event_desc    = request.form.get('eventdesc', '').strip()
            image_mode    = request.form.get('image_mode', 'rh_logo')
            image_url     = request.form.get('image_url', '').strip()

            if not event_name:
                return jsonify({'success': False, 'error': 'Event name is required'}), 400

            # --- MOCK (Phase 1) ---
            # Simulates what the CloudLink API will return after real registration.
            # Replace this block in Phase 2 with actual HTTP call to POST /register.
            mock_eventid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            mock_key     = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            # --- END MOCK ---

            # Save keys to RH database options so the main panel picks them up
            rhapi.db.set_option('cl-event-id', mock_eventid)
            rhapi.db.set_option('cl-event-key', mock_key)

            logger.info(f'[CloudLink] Mock event registered: {mock_eventid} for "{event_name}"')

            return jsonify({
                'success': True,
                'eventid': mock_eventid,
                'privatekey': mock_key,
            })

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
