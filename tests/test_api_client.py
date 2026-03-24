"""Tests for CloudLinkAPIClient — mock requests, verify error handling."""

import pytest
from unittest.mock import patch, MagicMock
from cloudlink.api_client import CloudLinkAPIClient


@pytest.fixture
def client():
    return CloudLinkAPIClient("https://api.test.com", timeout=5)


class TestRequest:
    @patch('cloudlink.api_client.requests')
    def test_successful_get(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"version": "1.5.0"}
        mock_requests.get.return_value = mock_resp
        mock_resp.raise_for_status = MagicMock()

        result = client.healthcheck()
        assert result == {"version": "1.5.0"}
        mock_requests.get.assert_called_once_with(
            "https://api.test.com/healthcheck", timeout=5
        )

    @patch('cloudlink.api_client.requests')
    def test_connection_error_returns_none(self, mock_requests, client):
        import requests as real_requests
        mock_requests.exceptions = real_requests.exceptions
        mock_requests.get.side_effect = real_requests.exceptions.ConnectionError()

        result = client.healthcheck()
        assert result is None

    @patch('cloudlink.api_client.requests')
    def test_timeout_returns_none(self, mock_requests, client):
        import requests as real_requests
        mock_requests.exceptions = real_requests.exceptions
        mock_requests.get.side_effect = real_requests.exceptions.Timeout()

        result = client.healthcheck()
        assert result is None

    @patch('cloudlink.api_client.requests')
    def test_http_error_returns_none(self, mock_requests, client):
        import requests as real_requests
        mock_requests.exceptions = real_requests.exceptions
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = real_requests.exceptions.HTTPError()
        mock_requests.get.return_value = mock_resp

        result = client.healthcheck()
        assert result is None


class TestPostMethods:
    @patch('cloudlink.api_client.requests')
    def test_post_class_success(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = client.post_class({"classid": 1})
        assert result is True
        mock_requests.post.assert_called_once_with(
            "https://api.test.com/class", json={"classid": 1}, timeout=5
        )

    @patch('cloudlink.api_client.requests')
    def test_post_class_failure(self, mock_requests, client):
        import requests as real_requests
        mock_requests.exceptions = real_requests.exceptions
        mock_requests.post.side_effect = real_requests.exceptions.ConnectionError()

        result = client.post_class({"classid": 1})
        assert result is False

    @patch('cloudlink.api_client.requests')
    def test_post_slots(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        assert client.post_slots({"heats": []}) is True

    @patch('cloudlink.api_client.requests')
    def test_post_laps(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        assert client.post_laps({"raceid": 1}) is True

    @patch('cloudlink.api_client.requests')
    def test_post_results(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        assert client.post_results({"results": []}) is True

    @patch('cloudlink.api_client.requests')
    def test_post_resync(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        assert client.post_resync({"data": "{}"}) is True


class TestDeleteMethods:
    @patch('cloudlink.api_client.requests')
    def test_delete_slots(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.delete.return_value = mock_resp

        assert client.delete_slots({"heatid": 1}) is True
        mock_requests.delete.assert_called_once()

    @patch('cloudlink.api_client.requests')
    def test_delete_class(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.delete.return_value = mock_resp

        assert client.delete_class({"classid": 1}) is True


class TestRegistrationMethods:
    @patch('cloudlink.api_client.requests')
    def test_register_event_success(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"eventid": "e1", "privatekey": "k1"}
        mock_requests.post.return_value = mock_resp

        result = client.register_event({"eventname": "Test"})
        assert result == {"eventid": "e1", "privatekey": "k1"}

    @patch('cloudlink.api_client.requests')
    def test_register_event_failure(self, mock_requests, client):
        import requests as real_requests
        mock_requests.exceptions = real_requests.exceptions
        mock_requests.post.side_effect = real_requests.exceptions.Timeout()

        result = client.register_event({"eventname": "Test"})
        assert result is None

    @patch('cloudlink.api_client.requests')
    def test_get_event_details(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"sk": "event#1"}]
        mock_requests.get.return_value = mock_resp

        result = client.get_event_details("evt-1")
        assert result == [{"sk": "event#1"}]

    @patch('cloudlink.api_client.requests')
    def test_patch_event(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_requests.patch.return_value = mock_resp

        result = client.patch_event("evt-1", "key-1", {"eventlogourl": "https://img.jpg"})
        assert result is True
        mock_requests.patch.assert_called_once_with(
            "https://api.test.com/event/evt-1",
            json={"eventlogourl": "https://img.jpg"},
            headers={"X-Private-Key": "key-1"},
            timeout=5,
        )


class TestImageUpload:
    @patch('cloudlink.api_client.requests')
    def test_presign_upload_success(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"data": {"uploadUrl": "https://s3/up", "publicUrl": "https://cdn/img"}}
        mock_requests.post.return_value = mock_resp

        result = client.presign_upload("photo.jpg", "image/jpeg")
        assert result["uploadUrl"] == "https://s3/up"
        assert result["publicUrl"] == "https://cdn/img"

    @patch('cloudlink.api_client.requests')
    def test_presign_upload_failure(self, mock_requests, client):
        import requests as real_requests
        mock_requests.exceptions = real_requests.exceptions
        mock_requests.post.side_effect = real_requests.exceptions.ConnectionError()

        result = client.presign_upload("photo.jpg", "image/jpeg")
        assert result is None

    @patch('cloudlink.api_client.requests')
    def test_upload_to_s3_success(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.put.return_value = mock_resp

        result = client.upload_to_s3("https://s3/up", b"image-bytes", "image/jpeg")
        assert result is True

    @patch('cloudlink.api_client.requests')
    def test_upload_to_s3_failure(self, mock_requests, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_requests.put.return_value = mock_resp

        result = client.upload_to_s3("https://s3/up", b"image-bytes", "image/jpeg")
        assert result is False
