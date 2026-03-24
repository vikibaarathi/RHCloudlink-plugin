import logging
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from .datamanager import ClDataManager
from .constants import CL_VERSION, OPT_ENABLED, OPT_EVENT_ID, OPT_EVENT_KEY
from .payloads import (
    build_class_payload, build_heat_slots_payload, build_delete_payload,
    build_laps_payload, build_result_entry, build_results_payload,
    build_resync_payload, format_heat_name,
)


class CloudLink():
    CL_FORCEUPDATE = False

    def __init__(self, rhapi, api_client=None):
        self.logger = logging.getLogger(__name__)
        self._rhapi = rhapi
        self._api_client = api_client
        self.cldatamanager = ClDataManager(self._rhapi)

    # ── Guard ────────────────────────────────────────────────────────────────

    def _ready(self):
        """Return event keys if plugin is enabled and keys are set, else None."""
        keys = self.getEventKeys()
        if not self.isEnabled() or not keys["notempty"]:
            return None
        return keys

    # ── Plugin lifecycle ─────────────────────────────────────────────────────

    def init_plugin(self, args):
        isEnabled = self.isEnabled()
        notEmptyKeys = self.getEventKeys()["notempty"]

        if isEnabled is False:
            self.logger.warning("Cloudlink is disabled. Please enable at Format page")
        elif notEmptyKeys is False:
            self.logger.warning("Cloudlink event keys are missing. Please register at https://rhcloudlink.com/register")
        else:
            respond = self._api_client.healthcheck()
            if respond is None:
                self.logger.warning("Cloudlink cannot connect to internet. Check connection and try again.")
            else:
                if CL_VERSION != respond["version"]:
                    if respond["softupgrade"] == True:
                        self.logger.warning("New version of Cloud Link is available. Please consider upgrading.")
                    if respond["forceupgrade"] == True:
                        self.logger.warning("Cloudlink plugin needs to be updated.")
                        self.CL_FORCEUPDATE = True
                self.logger.info("Cloudlink is ready")

        self.init_ui(args)

    def init_ui(self, args):
        ui = self._rhapi.ui
        ui.register_panel("cloud-link", "Cloudlink", "format")
        ui.register_quickbutton("cloud-link", "send-all-button", "Resync", self.resync_new)
        ui.register_markdown("cloud-link", "cl-setup-link",
            '<a href="/cloudlink/setup" class="button-like" style="display:inline-block;margin:4px 0;">'
            '⚙ Setup / Register Event</a>'
        )

        cl_enableplugin = UIField(name='cl-enable-plugin', label='Enable Cloud Link Plugin', field_type=UIFieldType.CHECKBOX, desc="Enable or disable this plugin.")
        cl_eventid  = UIField(name='cl-event-id',  label='Cloud Link Event ID',          field_type=UIFieldType.TEXT, desc="Event ID from rhcloudlink.com/register or the in-timer setup page.")
        cl_eventkey = UIField(name='cl-event-key', label='Cloud Link Event Private Key', field_type=UIFieldType.TEXT, desc="Private key provided after registration. Keep this safe.")

        fields = self._rhapi.fields
        fields.register_option(cl_enableplugin, "cloud-link")
        fields.register_option(cl_eventid,      "cloud-link")
        fields.register_option(cl_eventkey,     "cloud-link")

        # Register the Flask blueprint for the in-timer registration UI
        try:
            from .registration_blueprint import create_registration_blueprint
            bp = create_registration_blueprint(self._rhapi, self._api_client)
            self._rhapi.ui.blueprint_add(bp)
            self.logger.info("CloudLink: registration blueprint registered at /cloudlink/setup")
        except Exception as e:
            self.logger.error(f"CloudLink: failed to register blueprint: {e}")

    # ── Event handlers ───────────────────────────────────────────────────────

    def resync_new(self, args):
        keys = self._ready()
        if not keys:
            return
        data = self.cldatamanager.get_everything()
        ui = self._rhapi.ui
        ui.message_notify("Initializing resyncronization protocol...")
        payload = build_resync_payload(keys, data)
        if self._api_client.post_resync(payload):
            ui.message_notify("Records sent to cloud for processing. Check cloudlink for status")
        else:
            ui.message_notify("Failed to reach CloudLink API. Check connection and try again.")

    def class_listener(self, args):
        keys = self._ready()
        if not keys:
            self.logger.warning("Cloud-Link Disabled")
            return

        eventname = args["_eventName"]
        if eventname == "classAdd":
            classid = args["class_id"]
            classname = "Class " + str(classid)
            brackettype = "none"
            round_type = 0

        elif eventname == "classAlter":
            classid = args["class_id"]
            raceclass = self._rhapi.db.raceclass_by_id(classid)
            classname = raceclass.name
            brackettype = "check"
            round_type = 0
            if hasattr(raceclass, "round_type"):
                round_type = raceclass.round_type

        elif eventname == "heatGenerate":
            classid = args["output_class_id"]
            raceclass = self._rhapi.db.raceclass_by_id(classid)
            classname = raceclass.name if raceclass.name else "Class " + str(classid)
            brackettype = self.get_brackettype(args)
            round_type = 0
            if hasattr(raceclass, "round_type"):
                round_type = raceclass.round_type

        payload = build_class_payload(keys, classid, classname, brackettype, round_type)
        self._api_client.post_class(payload)

    def class_heat_delete(self, args):
        keys = self._ready()
        if not keys:
            return
        removaltype = args["_eventName"]
        entity_id = args.get("heat_id") if removaltype == "heatDelete" else args.get("class_id")
        endpoint, payload = build_delete_payload(keys, removaltype, entity_id)
        if endpoint == "/slots":
            self._api_client.delete_slots(payload)
        elif endpoint == "/class":
            self._api_client.delete_class(payload)

    def heat_listener(self, args):
        keys = self._ready()
        if not keys:
            self.logger.warning("Cloud-Link Disabled")
            return

        db = self._rhapi.db
        heat = db.heat_by_id(args["heat_id"])
        thisheat = self._build_heat_detail(heat, db)
        payload = build_heat_slots_payload(keys, [thisheat])
        self._api_client.post_slots(payload)

    def laptime_listener(self, args):
        keys = self._ready()
        if not keys:
            return

        raceid = args["race_id"]
        savedracemeta = self._rhapi.db.race_by_id(raceid)
        classid = savedracemeta.class_id
        heatid = savedracemeta.heat_id
        roundid = savedracemeta.round_id

        raceclass = self._rhapi.db.raceclass_by_id(classid)
        classname = raceclass.name

        raceresults = self._rhapi.db.race_results(raceid)
        primary_leaderboard = raceresults["meta"]["primary_leaderboard"]
        filteredraceresults = raceresults[primary_leaderboard]

        pilotruns = self._rhapi.db.pilotruns_by_race(raceid)
        pilotlaps = []
        for run in pilotruns:
            laps = self._rhapi.db.laps_by_pilotrun(run.id)
            for lap in laps:
                if lap.deleted == False:
                    pilotlaps.append({
                        "id": lap.id,
                        "race_id": lap.race_id,
                        "pilotrace_id": lap.pilotrace_id,
                        "pilot_id": lap.pilot_id,
                        "lap_time_stamp": lap.lap_time_stamp,
                        "lap_time": lap.lap_time,
                        "lap_time_formatted": lap.lap_time_formatted,
                        "deleted": lap.deleted,
                    })

        payload = build_laps_payload(keys, raceid, classid, classname, heatid,
                                     roundid, primary_leaderboard,
                                     filteredraceresults, pilotlaps)
        if self._api_client.post_laps(payload):
            self.logger.info("Laps sent to cloud")
        else:
            self.logger.error("Failed to send laps to cloud")

    def results_listener(self, args):
        keys = self._ready()
        self.laptime_listener(args)

        if not keys:
            self.logger.warning("Cloud-Link Disabled")
            return

        savedracemeta = self._rhapi.db.race_by_id(args["race_id"])
        classid = savedracemeta.class_id
        raceclass = self._rhapi.db.raceclass_by_id(classid)
        classname = raceclass.name
        ranking = raceclass.ranking

        db = self._rhapi.db
        fullresults = db.raceclass_results(classid)

        if fullresults is None:
            self.logger.info("No results available to resync")
            return

        meta = fullresults["meta"]
        primary_leaderboard = meta["primary_leaderboard"]
        filteredresults = fullresults[primary_leaderboard]

        resultpayload = [
            build_result_entry(classid, classname, result, primary_leaderboard)
            for result in filteredresults
        ]

        payload = build_results_payload(keys, ranking, resultpayload)
        if self._api_client.post_results(payload):
            self.logger.info("Results sent to cloud")
        else:
            self.logger.error("Failed to send results to cloud")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_heat_detail(self, heatobj, db):
        """Build a heat detail dict with slot information."""
        heatname = format_heat_name(heatobj.name, heatobj.id)
        heatid = str(heatobj.id)

        group_id = 0
        if hasattr(heatobj, "group_id"):
            group_id = heatobj.group_id

        heatclassid = str(heatobj.class_id)
        racechannels = self.cldatamanager.get_frequencies_list()

        thisheat = {
            "classid": heatclassid,
            "classname": "unsupported",
            "heatname": heatname,
            "heatid": heatid,
            "group_id": group_id,
            "slots": [],
        }
        slots = db.slots_by_heat(heatid)

        for slot in slots:
            if slot.node_index is not None:
                channel = racechannels[slot.node_index] if slot.node_index < len(racechannels) else "0"
                pilotcallsign = "-"
                if slot.pilot_id != 0:
                    pilot = db.pilot_by_id(slot.pilot_id)
                    if pilot is not None:
                        pilotcallsign = pilot.callsign
                thisslot = {
                    "nodeindex": slot.node_index,
                    "channel": channel,
                    "callsign": pilotcallsign,
                }
                if thisslot["channel"] != "0" and thisslot["channel"] != "00":
                    thisheat["slots"].append(thisslot)
        return thisheat

    def isEnabled(self):
        enabled = self._rhapi.db.option(OPT_ENABLED)
        if enabled == "1" and self.CL_FORCEUPDATE == False:
            return True
        else:
            if self.CL_FORCEUPDATE == True:
                self.logger.warning("Cloudlink requires a mandatory update. Please update and restart the timer. No results will be synced for now.")
            return False

    def getEventKeys(self):
        eventid = self._rhapi.db.option(OPT_EVENT_ID)
        eventkey = self._rhapi.db.option(OPT_EVENT_KEY)
        notempty = True if (eventid and eventkey) else False
        return {
            "notempty": notempty,
            "eventid": eventid,
            "eventkey": eventkey,
        }

    def get_brackettype(self, args):
        brackettype = args["generator"]
        if brackettype == "Regulation_bracket__double_elimination" or brackettype == "Regulation_bracket__single_elimination":
            generate_args = args["generate_args"]
            brackettype = brackettype + "_" + generate_args["standard"]
        return brackettype
