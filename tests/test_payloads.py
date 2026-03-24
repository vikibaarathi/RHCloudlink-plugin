"""Tests for pure payload-building functions — no mocking needed."""

from cloudlink.payloads import (
    _with_auth, format_heat_name, build_class_payload, build_heat_slots_payload,
    build_delete_payload, build_laps_payload, build_result_entry,
    build_results_payload, build_resync_payload,
)


KEYS = {"eventid": "evt-1", "eventkey": "key-1"}


class TestWithAuth:
    def test_injects_auth_keys(self):
        result = _with_auth(KEYS, {"foo": "bar"})
        assert result["eventid"] == "evt-1"
        assert result["privatekey"] == "key-1"
        assert result["foo"] == "bar"

    def test_does_not_mutate_original(self):
        payload = {"data": 123}
        result = _with_auth(KEYS, payload)
        assert "eventid" not in payload
        assert "eventid" in result


class TestFormatHeatName:
    def test_returns_name_when_valid(self):
        assert format_heat_name("Finals", 5) == "Finals"

    def test_defaults_when_none_string(self):
        assert format_heat_name("None", 3) == "Heat 3"

    def test_defaults_when_empty(self):
        assert format_heat_name("", 7) == "Heat 7"

    def test_defaults_when_actual_none(self):
        assert format_heat_name(None, 2) == "Heat 2"

    def test_preserves_numeric_name(self):
        assert format_heat_name("Round 1", 1) == "Round 1"


class TestBuildClassPayload:
    def test_structure(self):
        result = build_class_payload(KEYS, 1, "Open Class", "none", 0)
        assert result["eventid"] == "evt-1"
        assert result["privatekey"] == "key-1"
        assert result["classid"] == 1
        assert result["classname"] == "Open Class"
        assert result["brackettype"] == "none"
        assert result["round_type"] == 0


class TestBuildHeatSlotsPayload:
    def test_wraps_heats(self):
        heats = [{"heatid": 1, "slots": []}]
        result = build_heat_slots_payload(KEYS, heats)
        assert result["heats"] == heats
        assert result["eventid"] == "evt-1"


class TestBuildDeletePayload:
    def test_heat_delete(self):
        endpoint, payload = build_delete_payload(KEYS, "heatDelete", 42)
        assert endpoint == "/slots"
        assert payload["heatid"] == 42
        assert payload["eventid"] == "evt-1"

    def test_class_delete(self):
        endpoint, payload = build_delete_payload(KEYS, "classDelete", 7)
        assert endpoint == "/class"
        assert payload["classid"] == 7

    def test_unknown_event_returns_none(self):
        endpoint, payload = build_delete_payload(KEYS, "unknownEvent", 1)
        assert endpoint is None
        assert payload is None


class TestBuildLapsPayload:
    def test_structure(self):
        result = build_laps_payload(
            KEYS, race_id=10, class_id=2, class_name="Micro",
            heat_id=5, round_id=1, primary_leaderboard="by_fastest_lap",
            round_results=[{"pilot_id": 1}], pilot_laps=[{"id": 100}]
        )
        assert result["raceid"] == 10
        assert result["classid"] == 2
        assert result["classname"] == "Micro"
        assert result["heatid"] == 5
        assert result["roundid"] == 1
        assert result["method_label"] == "by_fastest_lap"
        assert result["roundresults"] == [{"pilot_id": 1}]
        assert result["pilotlaps"] == [{"id": 100}]


class TestBuildResultEntry:
    def test_full_result(self):
        result_data = {
            "pilot_id": 1, "callsign": "FPV_Ace", "position": 1,
            "consecutives": "12.345", "consecutives_base": 3,
            "laps": 10, "total_time": "120.5", "average_lap": "12.05",
            "fastest_lap": "11.2",
            "fastest_lap_source": {"round": 1, "heat": 2, "displayname": "Heat 2"},
            "consecutives_source": {"round": 1, "heat": 2, "displayname": "Heat 2"},
        }
        entry = build_result_entry(5, "Open", result_data, "by_fastest_lap")
        assert entry["classid"] == 5
        assert entry["classname"] == "Open"
        assert entry["pilot_id"] == 1
        assert entry["callsign"] == "FPV_Ace"
        assert entry["fastest_lap_source"]["round"] == 1
        assert entry["consecutives_source"]["displayname"] == "Heat 2"
        assert entry["method_label"] == "by_fastest_lap"

    def test_missing_sources(self):
        result_data = {
            "pilot_id": 2, "callsign": "Racer", "position": 2,
            "consecutives": "15.0", "consecutives_base": 3,
            "laps": 8, "total_time": "130.0", "average_lap": "16.25",
            "fastest_lap": "14.0",
        }
        entry = build_result_entry(1, "Micro", result_data, "by_consecutives")
        assert entry["fastest_lap_source"] is None
        assert entry["consecutives_source"] is None

    def test_none_sources(self):
        result_data = {
            "pilot_id": 3, "callsign": "Zoom", "position": 3,
            "consecutives": "20.0", "consecutives_base": 3,
            "laps": 5, "total_time": "100.0", "average_lap": "20.0",
            "fastest_lap": "18.0",
            "fastest_lap_source": None,
            "consecutives_source": None,
        }
        entry = build_result_entry(1, "Open", result_data, "by_fastest_lap")
        assert entry["fastest_lap_source"] is None
        assert entry["consecutives_source"] is None


class TestBuildResultsPayload:
    def test_structure(self):
        results = [{"pilot_id": 1}]
        ranking = {"method": "by_fastest_lap"}
        payload = build_results_payload(KEYS, ranking, results)
        assert payload["ranks"] == ranking
        assert payload["results"] == results
        assert payload["eventid"] == "evt-1"

    def test_none_ranking_becomes_empty_dict(self):
        payload = build_results_payload(KEYS, None, [])
        assert payload["ranks"] == {}

    def test_false_ranking_becomes_empty_dict(self):
        payload = build_results_payload(KEYS, False, [])
        assert payload["ranks"] == {}


class TestBuildResyncPayload:
    def test_structure(self):
        payload = build_resync_payload(KEYS, '{"pilots": []}')
        assert payload["data"] == '{"pilots": []}'
        assert payload["eventid"] == "evt-1"
