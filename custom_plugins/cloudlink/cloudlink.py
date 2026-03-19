import json
import requests
import logging
import threading
from datetime import datetime, timezone
from sqlalchemy.ext.declarative import DeclarativeMeta
from RHUI import UIField, UIFieldType, UIFieldSelectOption
from .datamanager import ClDataManager
try:
    from .config import CL_API_ENDPOINT as _CONFIGURED_ENDPOINT
except ImportError:
    _CONFIGURED_ENDPOINT = "https://api.rhcloudlink.com"

class CloudLink():
    CL_VERSION = "1.2.1"
    CL_API_ENDPOINT = _CONFIGURED_ENDPOINT
    CL_FORCEUPDATE = False

    def __init__(self,rhapi):
        self.logger = logging.getLogger(__name__)
        self._rhapi = rhapi
        self.cldatamanger = ClDataManager(self._rhapi)
        
    def init_plugin(self,args):

        isEnabled = self.isEnabled()
        isConnected = self.isConnected()
        notEmptyKeys = self.getEventKeys()["notempty"]

        if isEnabled is False:
            self.logger.warning("Cloudlink is disabled. Please enable at Format page")
        elif notEmptyKeys is False:
            self.logger.warning("Cloudlink event keys are missing. Please register at https://rhcloudlink.com/register")
        elif isConnected is False:
            self.logger.warning("Cloudlink cannot connect to internet. Check connection and try again.")
        else:
            x = requests.get(self.CL_API_ENDPOINT+'/healthcheck')
            respond = x.json()
            if self.CL_VERSION != respond["version"]:
                if respond["softupgrade"] == True:
                    self.logger.warning("New version of Cloud Link is available. Please consider upgrading.")

                if respond["forceupgrade"] == True:
                    self.logger.warning("Cloudlink plugin needs to bee updated. ")
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
            bp = create_registration_blueprint(self._rhapi)
            self._rhapi.ui.blueprint_add(bp)
            self.logger.info("CloudLink: registration blueprint registered at /cloudlink/setup")
        except Exception as e:
            self.logger.error(f"CloudLink: failed to register blueprint: {e}")

    def resync_new(self, args):
     
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            data = self.cldatamanger.get_everything()
            ui = self._rhapi.ui
            ui.message_notify("Initializing resyncronization protocol...")
            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"],
                "data": data         
            }

            x = requests.post(self.CL_API_ENDPOINT+"/resync", json = payload)
            ui.message_notify("Records sent to cloud for processing. Check cloudlink for status")

    def class_listener(self,args):
        
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            
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
                if raceclass.name == "":
                    classname = "Class " + str(classid)
                else:
                    classname = raceclass.name
                brackettype = self.get_brackettype(args)
                round_type = 0
                if hasattr(raceclass, "round_type"):
                    round_type = raceclass.round_type

            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"],
                "classid": classid,
                "classname": classname,
                "brackettype": brackettype,
                "round_type": round_type         
            }
            x = requests.post(self.CL_API_ENDPOINT+"/class", json = payload)
        else:
            self.logger.warning("Cloud-Link Disabled")

    def heat_generate(self,args):
        eventname = args["_eventName"]

    def class_heat_delete(self,args):
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            removaltype = args["_eventName"]
            if removaltype == "heatDelete":
                endpoint = "/slots"
                payload = {
                    "eventid": keys["eventid"],
                    "privatekey": keys["eventkey"],
                    "heatid": args["heat_id"]
                }

            elif removaltype == "classDelete":
                endpoint = "/class"
                payload = {
                    "eventid": keys["eventid"],
                    "privatekey": keys["eventkey"],
                    "classid": args["class_id"]
                }
            x = requests.delete(self.CL_API_ENDPOINT+endpoint, json = payload)  

    def heat_listener(self,args):
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:

            db = self._rhapi.db
            heat = db.heat_by_id(args["heat_id"])
            groups = []
            thisheat = self.getGroupingDetails(heat,db)
            groups.append(thisheat)

            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"],
                "heats": groups
            }
            x = requests.post(self.CL_API_ENDPOINT+"/slots", json = payload)
        else:
            self.logger.warning("Cloud-Link Disabled")

    def getGroupingDetails(self, heatobj, db):
        heatname = str(heatobj.name)
        heatid = str(heatobj.id)

        #Set group ID
        group_id = 0
        if hasattr(heatobj, "group_id"):
            group_id = heatobj.group_id

        #Default heat name if None
        if heatname == "None" or heatname == "":
            heatname = "Heat " + heatid

        heatclassid = str(heatobj.class_id)
        racechannels = self.getRaceChannels()

        thisheat = {
            "classid": heatclassid,
            "classname": "unsupported",
            "heatname": heatname,
            "heatid": heatid,
            "group_id": group_id,
            "slots":[]
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
                    "callsign": pilotcallsign
                }

                if (thisslot["channel"] != "0" and thisslot["channel"] != "00"):
                    thisheat["slots"].append(thisslot)
        return thisheat

    def getRaceChannels(self):

        frequencies = self._rhapi.race.frequencyset.frequencies
        
        freq = json.loads(frequencies)
        bands = freq["b"]
        channels = freq["c"]
        racechannels = []
        for i, band in enumerate(bands):
            racechannel = "0"
            if str(band) == 'None':
                racechannels.insert(i,racechannel)
            else:
                channel = channels[i]
                racechannel = str(band) + str(channel)
                racechannels.insert(i,racechannel)
        
        return racechannels

    def laptime_listener(self,args):
        
        #GET EVENT ID AND PRIVATE KEY
        keys = self.getEventKeys()

        if self.isConnected() and self.isEnabled() and keys["notempty"]:

            #GET THE ID information
            raceid = args["race_id"]

            savedracemeta = self._rhapi.db.race_by_id(raceid)
            classid = savedracemeta.class_id
            heatid = savedracemeta.heat_id
            roundid = savedracemeta.round_id

            raceclass = self._rhapi.db.raceclass_by_id(classid)
            classname = raceclass.name

            #ROUND SUMMARY - SUMMARY OF THIS PARTICULAR ROUND
            raceresults = self._rhapi.db.race_results(raceid)
            primary_leaderboard = raceresults["meta"]["primary_leaderboard"]
            filteredraceresults = raceresults[primary_leaderboard]

            #PILOT RUNS BY RACEID
            pilotruns = self._rhapi.db.pilotruns_by_race(raceid)

            pilotlaps = []
            for run in pilotruns:
                runid = run.id

                #LAPTIMES FOR INDIVIDUAL PILOT

                laps = self._rhapi.db.laps_by_pilotrun(runid)
                for lap in laps:

                    if lap.deleted == False:
                        thislap = {
                            "id": lap.id,
                            "race_id": lap.race_id,
                            "pilotrace_id": lap.pilotrace_id,
                            "pilot_id": lap.pilot_id,
                            "lap_time_stamp": lap.lap_time_stamp,
                            "lap_time": lap.lap_time,
                            "lap_time_formatted": lap.lap_time_formatted,
                            "deleted": lap.deleted
                        }
                        pilotlaps.append(thislap)

            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"],
                "raceid": raceid,
                "classid": classid,
                "classname": classname,
                "heatid": heatid,
                "roundid": roundid,
                "method_label": primary_leaderboard,
                "roundresults": filteredraceresults,
                "pilotlaps": pilotlaps

            }

            x = requests.post(self.CL_API_ENDPOINT+"/laps", json = payload)
            self.logger.info("Laps sent to cloud")
      
    def results_listener(self,args):
        
        keys = self.getEventKeys()

        self.laptime_listener(args)
        savedracemeta = self._rhapi.db.race_by_id(args["race_id"])
        classid = savedracemeta.class_id
  
        raceclass = self._rhapi.db.raceclass_by_id(classid)
        classname = raceclass.name
        ranking = raceclass.ranking
        
        if self.isConnected() and keys["notempty"]:

            # Send entire ranking object without filtering
            # Handle both None and False cases - use empty dict for consistent structure
            rankpayload = ranking if (ranking is not None and ranking is not False) else {}
            resultpayload = []     

            db = self._rhapi.db
            fullresults = db.raceclass_results(classid)

            if fullresults != None:
                meta = fullresults["meta"]
                primary_leaderboard = meta["primary_leaderboard"]         
                filteredresults = fullresults[primary_leaderboard]

                for result in filteredresults:
                    pilot = {
                        "classid": classid,
                        "classname": classname,
                        "pilot_id": result["pilot_id"],
                        "callsign": result["callsign"],
                        "position": result["position"],
                        "consecutives": result["consecutives"],
                        "consecutives_base" : result["consecutives_base"],
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
                    resultpayload.append(pilot)

                payload = {
                    "eventid": keys["eventid"],
                    "privatekey": keys["eventkey"],
                    "ranks": rankpayload,
                    "results": resultpayload
                }

                x = requests.post(self.CL_API_ENDPOINT+"/v2/results", json = payload)
                self.logger.info("Results sent to cloud")

            else:
                self.logger.info("No results available to resync")

        else:
            self.logger.warning("No internet connection available")

    # ── Live telemetry helpers ─────────────────────────────────────

    def _post_async(self, endpoint, payload):
        """Fire-and-forget POST in a background thread."""
        def _do_post():
            try:
                requests.post(self.CL_API_ENDPOINT + endpoint, json=payload, timeout=5)
            except Exception as e:
                self.logger.warning("CloudLink live POST %s failed: %s", endpoint, e)
        threading.Thread(target=_do_post, daemon=True).start()

    def _live_guard(self):
        """Return keys dict if live posting is allowed, else None."""
        keys = self.getEventKeys()
        if self.isEnabled() and keys["notempty"]:
            return keys
        return None

    def _utcnow(self):
        return datetime.now(timezone.utc).isoformat()

    # ── Live race lifecycle ──────────────────────────────────────

    def live_race_stage(self, args):
        keys = self._live_guard()
        if keys is None:
            return
        payload = {
            "eventId": keys["eventid"],
            "privateKey": keys["eventkey"],
            "status": "armed",
            "timestamp": self._utcnow()
        }
        self._post_async("/live/race", payload)
        self.logger.info("Live telemetry: race armed")

    def live_race_start(self, args):
        keys = self._live_guard()
        if keys is None:
            return
        payload = {
            "eventId": keys["eventid"],
            "privateKey": keys["eventkey"],
            "status": "racing",
            "timestamp": self._utcnow()
        }
        self._post_async("/live/race", payload)
        self.logger.info("Live telemetry: race started")

    def live_race_finish(self, args):
        keys = self._live_guard()
        if keys is None:
            return
        payload = {
            "eventId": keys["eventid"],
            "privateKey": keys["eventkey"],
            "status": "finished",
            "timestamp": self._utcnow()
        }
        self._post_async("/live/race", payload)
        self.logger.info("Live telemetry: race finished")

    # ── Live heat ────────────────────────────────────────────────

    def live_heat_set(self, args):
        keys = self._live_guard()
        if keys is None:
            return
        db = self._rhapi.db
        heat_id = args.get("heat_id")
        if heat_id is None:
            return
        heat = db.heat_by_id(heat_id)
        heat_name = heat.name if heat.name else "Heat " + str(heat_id)
        slots = db.slots_by_heat(heat_id)
        pilot_slots = []
        for slot in slots:
            if slot.node_index is not None and slot.pilot_id and slot.pilot_id != 0:
                pilot = db.pilot_by_id(slot.pilot_id)
                callsign = pilot.callsign if pilot else "-"
                pilot_slots.append({
                    "pilotId": slot.pilot_id,
                    "callsign": callsign,
                    "nodeIndex": slot.node_index
                })
        payload = {
            "eventId": keys["eventid"],
            "privateKey": keys["eventkey"],
            "heatId": heat_id,
            "heatName": heat_name,
            "pilotSlots": pilot_slots,
            "status": "set",
            "timestamp": self._utcnow()
        }
        self._post_async("/live/heat", payload)
        self.logger.info("Live telemetry: heat set — %s", heat_name)

    # ── Live lap ─────────────────────────────────────────────────

    def live_lap_recorded(self, args):
        keys = self._live_guard()
        if keys is None:
            return
        payload = {
            "eventId": keys["eventid"],
            "privateKey": keys["eventkey"],
            "pilotId": args.get("pilot_id"),
            "callsign": args.get("callsign", ""),
            "nodeIndex": args.get("node_index"),
            "lapNumber": args.get("lap_number"),
            "lapTimeMs": args.get("lap_time"),
            "lapTimeFormatted": args.get("lap_time_formatted", ""),
            "isHoleshot": args.get("is_holeshot", False),
            "timestamp": self._utcnow()
        }
        self._post_async("/live/lap", payload)

    def isConnected(self):
        try:
            response = requests.get(self.CL_API_ENDPOINT, timeout=5)
            return True
        except requests.ConnectionError:
            return False 
    
    def isEnabled(self):
        enabled = self._rhapi.db.option("cl-enable-plugin")

        if enabled == "1" and self.CL_FORCEUPDATE == False:

            return True
        else:
            if self.CL_FORCEUPDATE == True:
                self.logger.warning("Cloudlink requires a mandatory update. Please update and restart the timer. No results will be synced for now.")
            return False

    def getEventKeys(self):

        eventid = self._rhapi.db.option("cl-event-id")
        eventkey = self._rhapi.db.option("cl-event-key")
        notempty = True if (eventid and eventkey) else False
        keys = {
            "notempty": notempty,
            "eventid": eventid,
            "eventkey": eventkey
        }
        return keys

    def get_brackettype(self,args):
        
        brackettype = args["generator"]      
        if brackettype == "Regulation_bracket__double_elimination" or brackettype == "Regulation_bracket__single_elimination":
            generate_args = args["generate_args"]
            brackettype = brackettype+"_"+generate_args["standard"]    
        return brackettype

    
