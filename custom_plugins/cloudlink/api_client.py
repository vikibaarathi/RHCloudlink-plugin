"""HTTP transport layer for the CloudLink API."""

import logging
import requests
from .constants import API_TIMEOUT, S3_TIMEOUT


class CloudLinkAPIClient:
    """Handles all HTTP communication with the CloudLink API."""

    def __init__(self, base_url, timeout=API_TIMEOUT, logger=None):
        self._base_url = base_url.rstrip('/')
        self._timeout = timeout
        self._logger = logger or logging.getLogger(__name__)

    def _request(self, method, path, **kwargs):
        """Internal: make an HTTP request with error handling and timeout."""
        kwargs.setdefault('timeout', self._timeout)
        url = self._base_url + path
        resp = None
        try:
            resp = getattr(requests, method)(url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.ConnectionError:
            self._logger.error(f"CloudLink: cannot reach {url}")
            return None
        except requests.exceptions.Timeout:
            self._logger.error(f"CloudLink: timeout on {url}")
            return None
        except requests.exceptions.HTTPError as exc:
            status = resp.status_code if resp is not None else "?"
            body = resp.text[:200] if resp is not None else str(exc)
            self._logger.error(f"CloudLink: HTTP {status} from {url}: {body}")
            return None

    # ── Core plugin endpoints ────────────────────────────────────────────

    def healthcheck(self):
        """GET /healthcheck — returns parsed JSON or None."""
        resp = self._request('get', '/healthcheck')
        return resp.json() if resp is not None else None

    def post_class(self, payload):
        """POST /class — send class metadata."""
        return self._request('post', '/class', json=payload) is not None

    def post_slots(self, payload):
        """POST /slots — send heat/slot data."""
        return self._request('post', '/slots', json=payload) is not None

    def delete_slots(self, payload):
        """DELETE /slots — remove a heat."""
        return self._request('delete', '/slots', json=payload) is not None

    def delete_class(self, payload):
        """DELETE /class — remove a class."""
        return self._request('delete', '/class', json=payload) is not None

    def post_laps(self, payload):
        """POST /laps — send lap times."""
        return self._request('post', '/laps', json=payload) is not None

    def post_results(self, payload):
        """POST /v2/results — send class results."""
        return self._request('post', '/v2/results', json=payload) is not None

    def post_resync(self, payload):
        """POST /resync — send full event data."""
        return self._request('post', '/resync', json=payload) is not None

    # ── Registration / event management endpoints ────────────────────────

    def register_event(self, payload):
        """POST /register — returns parsed JSON or None."""
        resp = self._request('post', '/register', json=payload)
        return resp.json() if resp is not None else None

    def get_event_details(self, event_id):
        """GET /event?eventid=... — returns parsed JSON or None."""
        resp = self._request('get', '/event', params={'eventid': event_id})
        return resp.json() if resp is not None else None

    def patch_event(self, event_id, private_key, data):
        """PATCH /event/{id} — update event metadata."""
        resp = self._request('patch', f'/event/{event_id}',
                             json=data,
                             headers={'X-Private-Key': private_key})
        return resp is not None

    # ── Image upload endpoints ───────────────────────────────────────────

    def presign_upload(self, file_name, content_type):
        """POST /uploads/presign — returns {'uploadUrl': ..., 'publicUrl': ...} or None."""
        resp = self._request('post', '/uploads/presign',
                             json={'fileName': file_name, 'contentType': content_type})
        if resp is not None:
            return resp.json().get('data', {})
        return None

    def upload_to_s3(self, upload_url, file_bytes, content_type):
        """PUT to S3 presigned URL — returns True on success."""
        try:
            resp = requests.put(
                upload_url,
                data=file_bytes,
                headers={'Content-Type': content_type},
                timeout=S3_TIMEOUT
            )
            return resp.status_code in (200, 204)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            self._logger.error(f"CloudLink: S3 upload failed: {e}")
            return False
