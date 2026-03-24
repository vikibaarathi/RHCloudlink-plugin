"""Pure payload-building functions for the CloudLink API.

All functions in this module are pure — no side effects, no rhapi dependency,
no HTTP calls. They transform data into the dict shapes the API expects.
"""


def _with_auth(keys, payload):
    """Inject event authentication into a payload."""
    return {"eventid": keys["eventid"], "privatekey": keys["eventkey"], **payload}


def format_heat_name(name, heat_id):
    """Return a display name for a heat, defaulting to 'Heat {id}' if empty/None."""
    name_str = str(name)
    if name_str == "None" or name_str == "":
        return "Heat " + str(heat_id)
    return name_str


def build_class_payload(keys, class_id, class_name, bracket_type, round_type):
    """Build payload for POST /class."""
    return _with_auth(keys, {
        "classid": class_id,
        "classname": class_name,
        "brackettype": bracket_type,
        "round_type": round_type,
    })


def build_heat_slots_payload(keys, heats):
    """Build payload for POST /slots."""
    return _with_auth(keys, {"heats": heats})


def build_delete_payload(keys, event_name, entity_id):
    """Build payload and endpoint for DELETE /slots or /class.

    Returns (endpoint, payload) tuple.
    """
    if event_name == "heatDelete":
        return "/slots", _with_auth(keys, {"heatid": entity_id})
    elif event_name == "classDelete":
        return "/class", _with_auth(keys, {"classid": entity_id})
    return None, None


def build_laps_payload(keys, race_id, class_id, class_name, heat_id, round_id,
                       primary_leaderboard, round_results, pilot_laps):
    """Build payload for POST /laps."""
    return _with_auth(keys, {
        "raceid": race_id,
        "classid": class_id,
        "classname": class_name,
        "heatid": heat_id,
        "roundid": round_id,
        "method_label": primary_leaderboard,
        "roundresults": round_results,
        "pilotlaps": pilot_laps,
    })


def build_result_entry(class_id, class_name, result, primary_leaderboard):
    """Build a single result entry dict from a race result.

    Shared between results_listener (real-time) and datamanager (resync).
    """
    return {
        "classid": class_id,
        "classname": class_name,
        "pilot_id": result["pilot_id"],
        "callsign": result["callsign"],
        "position": result["position"],
        "consecutives": result["consecutives"],
        "consecutives_base": result["consecutives_base"],
        "laps": result["laps"],
        "total_time": result["total_time"],
        "average_lap": result["average_lap"],
        "fastest_lap": result["fastest_lap"],
        "method_label": primary_leaderboard,
        "fastest_lap_source": {
            "round": result["fastest_lap_source"]["round"],
            "heat": result["fastest_lap_source"]["heat"],
            "displayname": result["fastest_lap_source"]["displayname"],
        } if "fastest_lap_source" in result and result["fastest_lap_source"] is not None else None,
        "consecutives_source": {
            "round": result["consecutives_source"]["round"],
            "heat": result["consecutives_source"]["heat"],
            "displayname": result["consecutives_source"]["displayname"],
        } if "consecutives_source" in result and result["consecutives_source"] is not None else None,
    }


def build_results_payload(keys, ranking, results):
    """Build payload for POST /v2/results."""
    rankpayload = ranking if (ranking is not None and ranking is not False) else {}
    return _with_auth(keys, {
        "ranks": rankpayload,
        "results": results,
    })


def build_resync_payload(keys, data):
    """Build payload for POST /resync."""
    return _with_auth(keys, {"data": data})
