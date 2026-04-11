"""
LiveSync — Real-time lap streaming to CloudLink.

Listens to RotorHazard race lifecycle events (start, lap recorded, stop)
and pushes lightweight payloads to the CloudLink API for live leaderboard
display on remote clients.

This module is intentionally decoupled from the main cloudlink.py sync logic.
The existing LAPS_SAVE / LAPS_RESAVE flow remains the source of truth for
finalized results.  LiveSync provides a *preview* stream during active races.
"""

import logging
import requests


class LiveSync:
    """Streams live race data to CloudLink cloud endpoints."""

    LIVE_LAP_PATH = "/live/lap"
    LIVE_STATUS_PATH = "/live/race-status"
    REQUEST_TIMEOUT_SECS = 2

    def __init__(self, rhapi, get_keys_fn, is_ready_fn, api_endpoint):
        """
        Args:
            rhapi:          RotorHazard plugin API instance.
            get_keys_fn:    Callable returning {"notempty": bool, "eventid": str, "eventkey": str}.
            is_ready_fn:    Callable returning True when the plugin is connected and enabled.
            api_endpoint:   Base URL of the CloudLink API (e.g. "https://api.rhcloudlink.com").
        """
        self.logger = logging.getLogger(__name__)
        self._rhapi = rhapi
        self._get_keys = get_keys_fn
        self._is_ready = is_ready_fn
        self._api_endpoint = api_endpoint

    # ------------------------------------------------------------------
    # Event handlers (registered in __init__.py)
    # ------------------------------------------------------------------

    def on_race_start(self, args):
        """Handle Evt.RACE_START — broadcast pilot lineup for the new race."""
        if not self._is_ready():
            return

        keys = self._get_keys()
        if not keys["notempty"]:
            return

        race = self._rhapi.race
        heat_id = race.heat
        heat_data = self._rhapi.db.heat_by_id(heat_id)
        heat_name = heat_data.display_name if heat_data and hasattr(heat_data, 'display_name') else (
            heat_data.name if heat_data and hasattr(heat_data, 'name') else f"Heat {heat_id}"
        )
        class_id = heat_data.class_id if heat_data else 0

        round_id = self._resolve_round_id(heat_id)
        pilots = self._build_pilot_list(heat_id, race)

        payload = {
            "eventid": keys["eventid"],
            "privatekey": keys["eventkey"],
            "status": "racing",
            "heatid": heat_id,
            "heatname": heat_name,
            "classid": class_id,
            "roundid": round_id,
            "pilots": pilots,
        }

        self._post(self.LIVE_STATUS_PATH, payload)
        self.logger.info("Live race start broadcast — heat %s, %d pilots", heat_id, len(pilots))

    def on_lap_recorded(self, args):
        """Handle Evt.RACE_LAP_RECORDED — push a single lap to the cloud.

        The ``lap`` value in *args* is a :class:`RHRace.Crossing` dataclass
        instance — fields are accessed as attributes, not dict keys.
        """
        if not self._is_ready():
            return

        keys = self._get_keys()
        if not keys["notempty"]:
            return

        lap = args.get("lap")
        if lap is None:
            return

        # Skip deleted / invalid crossings
        if getattr(lap, "deleted", False) or getattr(lap, "invalid", False):
            return

        pilot_id = args.get("pilot_id")
        callsign = self._resolve_callsign(pilot_id)

        race = self._rhapi.race
        heat_id = race.heat
        heat_data = self._rhapi.db.heat_by_id(heat_id)
        class_id = heat_data.class_id if heat_data else 0
        round_id = self._resolve_round_id(heat_id)

        payload = {
            "eventid": keys["eventid"],
            "privatekey": keys["eventkey"],
            "heatid": heat_id,
            "classid": class_id,
            "roundid": round_id,
            "pilot_id": pilot_id,
            "callsign": callsign,
            "node_index": args.get("node_index"),
            "color": args.get("color", ""),
            "lap_number": getattr(lap, "lap_number", 0),
            "lap_time": getattr(lap, "lap_time", 0),
            "lap_time_formatted": getattr(lap, "lap_time_formatted", ""),
            "lap_time_stamp": getattr(lap, "lap_time_stamp", 0),
            "deleted": bool(getattr(lap, "deleted", False)),
        }

        self._post(self.LIVE_LAP_PATH, payload)
        self.logger.debug(
            "Live lap sent — pilot %s lap %s (%s)",
            callsign,
            getattr(lap, "lap_number", "?"),
            getattr(lap, "lap_time_formatted", "?"),
        )

    def on_heat_set(self, args):
        """Handle Evt.HEAT_SET — broadcast the newly selected heat to viewers."""
        if not self._is_ready():
            return

        keys = self._get_keys()
        if not keys["notempty"]:
            return

        heat_id = args.get("heat_id")
        if heat_id is None:
            return

        heat_data = self._rhapi.db.heat_by_id(heat_id)
        heat_name = heat_data.display_name if heat_data and hasattr(heat_data, 'display_name') else (
            heat_data.name if heat_data and hasattr(heat_data, 'name') else f"Heat {heat_id}"
        )
        class_id = heat_data.class_id if heat_data else 0
        round_id = self._resolve_round_id(heat_id)
        pilots = self._build_pilot_list(heat_id, self._rhapi.race)

        payload = {
            "eventid": keys["eventid"],
            "privatekey": keys["eventkey"],
            "status": "heat_set",
            "heatid": heat_id,
            "heatname": heat_name,
            "classid": class_id,
            "roundid": round_id,
            "pilots": pilots,
        }

        self._post(self.LIVE_STATUS_PATH, payload)
        self.logger.info("Live heat set broadcast — heat %s (%s)", heat_id, heat_name)

    def on_race_stop(self, args):
        """Handle Evt.RACE_STOP — signal that the race has ended."""
        if not self._is_ready():
            return

        keys = self._get_keys()
        if not keys["notempty"]:
            return

        race = self._rhapi.race
        heat_id = race.heat
        heat_data = self._rhapi.db.heat_by_id(heat_id)
        class_id = heat_data.class_id if heat_data else 0
        round_id = self._resolve_round_id(heat_id)

        payload = {
            "eventid": keys["eventid"],
            "privatekey": keys["eventkey"],
            "status": "stopped",
            "heatid": heat_id,
            "classid": class_id,
            "roundid": round_id,
        }

        self._post(self.LIVE_STATUS_PATH, payload)
        self.logger.info("Live race stop broadcast — heat %s", heat_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_pilot_list(self, heat_id, race):
        """Build the pilot lineup for a heat, including callsign and seat color."""
        pilots = []
        slots = self._rhapi.db.slots_by_heat(heat_id)

        for slot in slots:
            if slot.node_index is None:
                continue
            if slot.pilot_id == 0:
                continue

            pilot = self._rhapi.db.pilot_by_id(slot.pilot_id)
            callsign = pilot.callsign if pilot else "-"
            color = self._safe_seat_color(race, slot.node_index)

            pilots.append({
                "pilot_id": slot.pilot_id,
                "callsign": callsign,
                "node_index": slot.node_index,
                "color": color,
            })

        return pilots

    def _resolve_callsign(self, pilot_id):
        """Look up a pilot's callsign by ID, returning '-' on failure."""
        if not pilot_id:
            return "-"
        try:
            pilot = self._rhapi.db.pilot_by_id(pilot_id)
            return pilot.callsign if pilot else "-"
        except Exception:
            return "-"

    def _resolve_round_id(self, heat_id):
        """Determine the next round number for the given heat."""
        try:
            saved = self._rhapi.db.races_by_heat(heat_id)
            return len(saved) + 1 if saved else 1
        except Exception:
            return 1

    def _safe_seat_color(self, race, node_index):
        """Safely read the seat color for a node, returning empty string on failure."""
        try:
            colors = race.seat_colors
            if colors and node_index < len(colors):
                return str(colors[node_index])
        except Exception:
            pass
        return ""

    def _post(self, path, payload):
        """Fire-and-forget POST to the CloudLink API.

        Failures are logged but never raised — a missed live update is
        acceptable because the final LAPS_SAVE sync is the source of truth.
        """
        url = self._api_endpoint + path
        try:
            requests.post(url, json=payload, timeout=self.REQUEST_TIMEOUT_SECS)
        except requests.Timeout:
            self.logger.warning("Live sync timed out: %s", path)
        except requests.ConnectionError:
            self.logger.warning("Live sync connection failed: %s", path)
        except Exception as exc:
            self.logger.error("Live sync unexpected error: %s — %s", path, exc)
