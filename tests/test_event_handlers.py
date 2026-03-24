"""Tests for CloudLink event handlers — mock api_client + rhapi."""

import pytest
from unittest.mock import MagicMock, patch
from cloudlink.cloudlink import CloudLink


@pytest.fixture
def cloudlink(mock_rhapi, mock_api_client):
    return CloudLink(mock_rhapi, mock_api_client)


class TestReady:
    def test_returns_keys_when_enabled(self, cloudlink):
        keys = cloudlink._ready()
        assert keys is not None
        assert keys["eventid"] == "test-event-123"

    def test_returns_none_when_disabled(self, cloudlink, mock_rhapi):
        mock_rhapi.db.option = MagicMock(side_effect=lambda k: "0" if k == "cl-enable-plugin" else "val")
        assert cloudlink._ready() is None

    def test_returns_none_when_keys_missing(self, cloudlink, mock_rhapi):
        mock_rhapi.db.option = MagicMock(return_value="")
        assert cloudlink._ready() is None


class TestClassListener:
    def test_class_add(self, cloudlink, mock_api_client):
        cloudlink.class_listener({"_eventName": "classAdd", "class_id": 5})
        mock_api_client.post_class.assert_called_once()
        payload = mock_api_client.post_class.call_args[0][0]
        assert payload["classid"] == 5
        assert payload["classname"] == "Class 5"
        assert payload["brackettype"] == "none"

    def test_class_alter(self, cloudlink, mock_rhapi, mock_api_client):
        mock_class = MagicMock()
        mock_class.name = "Open Class"
        mock_class.round_type = 2
        mock_rhapi.db.raceclass_by_id.return_value = mock_class

        cloudlink.class_listener({"_eventName": "classAlter", "class_id": 3})
        payload = mock_api_client.post_class.call_args[0][0]
        assert payload["classname"] == "Open Class"
        assert payload["brackettype"] == "check"
        assert payload["round_type"] == 2

    def test_heat_generate(self, cloudlink, mock_rhapi, mock_api_client):
        mock_class = MagicMock()
        mock_class.name = "Bracket A"
        mock_class.round_type = 0
        mock_rhapi.db.raceclass_by_id.return_value = mock_class

        cloudlink.class_listener({
            "_eventName": "heatGenerate",
            "output_class_id": 2,
            "generator": "some_generator",
        })
        payload = mock_api_client.post_class.call_args[0][0]
        assert payload["classname"] == "Bracket A"

    def test_disabled_logs_warning(self, cloudlink, mock_rhapi, mock_api_client):
        mock_rhapi.db.option = MagicMock(side_effect=lambda k: "0" if k == "cl-enable-plugin" else "val")
        cloudlink.class_listener({"_eventName": "classAdd", "class_id": 1})
        mock_api_client.post_class.assert_not_called()


class TestClassHeatDelete:
    def test_heat_delete(self, cloudlink, mock_api_client):
        cloudlink.class_heat_delete({"_eventName": "heatDelete", "heat_id": 10})
        mock_api_client.delete_slots.assert_called_once()
        payload = mock_api_client.delete_slots.call_args[0][0]
        assert payload["heatid"] == 10

    def test_class_delete(self, cloudlink, mock_api_client):
        cloudlink.class_heat_delete({"_eventName": "classDelete", "class_id": 3})
        mock_api_client.delete_class.assert_called_once()
        payload = mock_api_client.delete_class.call_args[0][0]
        assert payload["classid"] == 3

    def test_disabled_does_nothing(self, cloudlink, mock_rhapi, mock_api_client):
        mock_rhapi.db.option = MagicMock(side_effect=lambda k: "0" if k == "cl-enable-plugin" else "val")
        cloudlink.class_heat_delete({"_eventName": "heatDelete", "heat_id": 1})
        mock_api_client.delete_slots.assert_not_called()


class TestHeatListener:
    def test_sends_heat_slots(self, cloudlink, mock_rhapi, mock_api_client):
        mock_heat = MagicMock()
        mock_heat.id = 5
        mock_heat.name = "Heat 5"
        mock_heat.class_id = 1
        mock_heat.group_id = 0
        mock_rhapi.db.heat_by_id.return_value = mock_heat
        mock_rhapi.db.slots_by_heat.return_value = []
        mock_rhapi.race.frequencyset.frequencies = '{"b":["R","R"],"c":["1","2"]}'

        cloudlink.heat_listener({"heat_id": 5})
        mock_api_client.post_slots.assert_called_once()
        payload = mock_api_client.post_slots.call_args[0][0]
        assert "heats" in payload
        assert len(payload["heats"]) == 1


class TestResyncNew:
    def test_calls_post_resync(self, cloudlink, mock_api_client):
        cloudlink.cldatamanager = MagicMock()
        cloudlink.cldatamanager.get_everything.return_value = '{"pilots": []}'

        cloudlink.resync_new({})
        mock_api_client.post_resync.assert_called_once()
        payload = mock_api_client.post_resync.call_args[0][0]
        assert payload["data"] == '{"pilots": []}'

    def test_shows_error_on_failure(self, cloudlink, mock_rhapi, mock_api_client):
        cloudlink.cldatamanager = MagicMock()
        cloudlink.cldatamanager.get_everything.return_value = '{}'
        mock_api_client.post_resync.return_value = False

        cloudlink.resync_new({})
        mock_rhapi.ui.message_notify.assert_called()
        last_msg = mock_rhapi.ui.message_notify.call_args[0][0]
        assert "Failed" in last_msg


class TestResultsListener:
    def test_sends_laps_and_results(self, cloudlink, mock_rhapi, mock_api_client):
        # Setup race metadata
        mock_race = MagicMock()
        mock_race.class_id = 1
        mock_race.heat_id = 2
        mock_race.round_id = 1
        mock_rhapi.db.race_by_id.return_value = mock_race

        # Setup class
        mock_class = MagicMock()
        mock_class.name = "Open"
        mock_class.ranking = {"method": "by_fastest_lap"}
        mock_rhapi.db.raceclass_by_id.return_value = mock_class

        # Setup race results (for laptime_listener)
        mock_rhapi.db.race_results.return_value = {
            "meta": {"primary_leaderboard": "by_fastest_lap"},
            "by_fastest_lap": [{"pilot_id": 1, "callsign": "Ace", "position": 1}],
        }
        mock_rhapi.db.pilotruns_by_race.return_value = []

        # Setup class results (for results_listener)
        mock_rhapi.db.raceclass_results.return_value = {
            "meta": {"primary_leaderboard": "by_fastest_lap"},
            "by_fastest_lap": [{
                "pilot_id": 1, "callsign": "Ace", "position": 1,
                "consecutives": "10.0", "consecutives_base": 3,
                "laps": 10, "total_time": "100.0", "average_lap": "10.0",
                "fastest_lap": "9.5",
                "fastest_lap_source": None, "consecutives_source": None,
            }],
        }

        cloudlink.results_listener({"race_id": 99})

        # Should call both laps and results
        mock_api_client.post_laps.assert_called_once()
        mock_api_client.post_results.assert_called_once()

        results_payload = mock_api_client.post_results.call_args[0][0]
        assert results_payload["ranks"] == {"method": "by_fastest_lap"}
        assert len(results_payload["results"]) == 1
        assert results_payload["results"][0]["callsign"] == "Ace"
