"""Shared fixtures for CloudLink plugin tests."""

import sys
import os
import pytest
from unittest.mock import MagicMock

# Add the custom_plugins directory to sys.path so we can import cloudlink
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'custom_plugins'))

# Stub out external dependencies that aren't available in test environment
sys.modules['eventmanager'] = MagicMock()
sys.modules['RHUI'] = MagicMock()


@pytest.fixture
def mock_rhapi():
    """Fake rhapi with db, race, ui, fields, events attributes."""
    rhapi = MagicMock()

    # DB options store
    _options = {
        'cl-enable-plugin': '1',
        'cl-event-id': 'test-event-123',
        'cl-event-key': 'test-key-456',
    }
    rhapi.db.option = MagicMock(side_effect=lambda key: _options.get(key))
    rhapi.db.option_set = MagicMock(side_effect=lambda key, val: _options.__setitem__(key, val))

    return rhapi


@pytest.fixture
def mock_api_client():
    """CloudLinkAPIClient with all methods returning success."""
    client = MagicMock()
    client.healthcheck.return_value = {"version": "1.5.0", "softupgrade": False, "forceupgrade": False}
    client.post_class.return_value = True
    client.post_slots.return_value = True
    client.delete_slots.return_value = True
    client.delete_class.return_value = True
    client.post_laps.return_value = True
    client.post_results.return_value = True
    client.post_resync.return_value = True
    client.register_event.return_value = {"eventid": "new-event-1", "privatekey": "new-key-1"}
    client.get_event_details.return_value = [{"sk": "event#123", "eventname": "Test Race"}]
    client.presign_upload.return_value = {"uploadUrl": "https://s3.example.com/upload", "publicUrl": "https://cdn.example.com/img.jpg"}
    client.upload_to_s3.return_value = True
    client.patch_event.return_value = True
    return client


@pytest.fixture
def sample_keys():
    """Standard event keys dict."""
    return {
        "notempty": True,
        "eventid": "test-event-123",
        "eventkey": "test-key-456",
    }
