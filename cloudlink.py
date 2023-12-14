import json
import requests
import logging
from sqlalchemy.ext.declarative import DeclarativeMeta
from RHUI import UIField, UIFieldType
from .datamanager import ClDataManager

class AlchemyEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                data = obj.__getattribute__(field)
                try:
                    json.dumps(data) # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
            # a json-encodable dict
            return fields

        return json.JSONEncoder.default(self, obj)
class CloudLink():
    CL_VERSION = "1.0.0"
    CL_API_ENDPOINT = "https://api.rhcloudlink.com"
    CL_FORCEUPDATE = False

    def __init__(self,rhapi):
        self.logger = logging.getLogger(__name__)
        self._rhapi = rhapi
        
    def init_plugin(self,args):
        
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            x = requests.get(self.CL_API_ENDPOINT+'/healthcheck')
            respond = x.json()
            if self.CL_VERSION != respond["version"]:
                if respond["softupgrade"] == True:
                    self.logger.warning("New version of Cloud Link is available. Please consider upgrading.")

                if respond["forceupgrade"] == True:
                    self.logger.warning("Cloudlink plugin needs to bee updated. ")
                    self.CL_FORCEUPDATE = True
            self.logger.info("Cloud-Link plugin ready to go.")
        else:
            self.logger.warning("No internet connection available")
        
        self.init_ui(args)
        
    def init_ui(self,args):
        ui = self._rhapi.ui
        ui.register_panel("cloud-link", "Cloudlink", "format")
        ui.register_quickbutton("cloud-link", "send-all-button", "Resync", self.resync_new)

        cl_enableplugin = UIField(name = 'cl-enable-plugin', label = 'Enable Cloud Link Plugin', field_type = UIFieldType.CHECKBOX, desc = "Enable or disable this plugin. Unchecking this box will stop all communication with the Cloudlink server.")
        cl_eventid = UIField(name = 'cl-event-id', label = 'Cloud Link Event ID', field_type = UIFieldType.TEXT, desc = "Event must be registered at rhcloudlink.com")
        cl_eventkey = UIField(name = 'cl-event-key', label = 'Cloud Link Event Private Key', field_type = UIFieldType.TEXT, desc = "Authentication key provided by Cloudlink during event registration.")

        fields = self._rhapi.fields
        fields.register_option(cl_enableplugin, "cloud-link")
        fields.register_option(cl_eventid, "cloud-link")
        fields.register_option(cl_eventkey, "cloud-link")

    def resync_new(self, args):

          resyncmanager = ClDataManager(self._rhapi)
          data = resyncmanager.get_everything()
          with open("cloudlink.json", "w") as outfile:
            outfile.write(data)

    def resync_start(self,args):
        ui = self._rhapi.ui
        ui.message_notify("Initializing resyncronization protocol...")
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:

            r = requests.get(self.CL_API_ENDPOINT+"/event?eventid="+keys["eventid"])
            r.raise_for_status()
            response = r.json()

            bracketlist = []
            for i in response:
                if i["sk"] != "event":
                    bracketlist.append(i)
            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"]         
            }

            try:
                x = requests.delete(self.CL_API_ENDPOINT+"/event", json = payload)
                x.raise_for_status()
                response = x.json()

                if response == "All records removed":
                    self.logger.info("All cloud records removed")
                    self.resend_everything(bracketlist)

            except Exception as err:
                self.logger.warning(f'Other error occurred: {err}')

    def resend_everything(self, bracketlist):

        ui = self._rhapi.ui

        #GET ALL CLASSES
        db = self._rhapi.db
        classes = db.raceclasses

        total = len(classes)
        for idx, clss in enumerate(classes):
            brackettype = "none"
            #GET 1 CLASS
            classid = clss.id
            for i in bracketlist:
                if i["classid"] ==  classid:
                    brackettype = i["brackettype"]

                    
            

            #check class name if blank
            if clss.name == '':
                classname = "Class "+str(classid)
            else:
                classname = clss.name
            args = {
                "_eventName": "resync",
                "classid": classid,
                "classname": classname,
                "brackettype": brackettype
            }
            logging.info(args)
            self.class_listener(args)

            #GET ALL HEATS FROM THIS CLASS
            heats = db.heats_by_class(classid)

            for heat in heats:
                args = {
                    "_eventName": "resync",
                    "heat_id": heat.id
                }

                logging.info(args)
                self.heat_listener(args)

            #GET RESULTS FOR THIS CLASS
            resultargs = {
                "_eventName": "resync",
                "classid": classid
            }
            self.results_listener(resultargs)

            allraces = self._rhapi.db.races_by_raceclass(classid)
            for race in allraces:

                lapsargs = {
                    "_eventName": "resync",
                    "race_id": race.id
                }

                self.laptime_listener(lapsargs)

            

            uimessage = str(idx + 1)+"/"+str(total)+" classes successfully synced..."
            ui.message_notify(uimessage)

        return True

    def class_listener(self,args):
        
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            
            eventname = args["_eventName"]
            if eventname == "classAdd":
                classid = args["class_id"]
                classname = "Class " + str(classid)
                brackettype = "none"

            elif eventname == "classAlter":
                classid = args["class_id"]
                raceclass = self._rhapi.db.raceclass_by_id(classid)
                classname = raceclass.name
                brackettype = "check"

            elif eventname == "heatGenerate":
                classid = args["output_class_id"]
                raceclass = self._rhapi.db.raceclass_by_id(classid)
                if raceclass.name == "":
                    classname = "Class " + str(classid)
                else:
                    classname = raceclass.name
                brackettype = self.get_brackettype(args)

            elif eventname == "resync":
                classid = args["classid"]
                classname = args["classname"]
                brackettype = args["brackettype"] 
                

            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"],
                "classid": classid,
                "classname": classname,
                "brackettype": brackettype         
            }

            x = requests.post(self.CL_API_ENDPOINT+"/class", json = payload)
        else:
            self.logger.warning("Cloud-Link Disabled")


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

        #Default heat name if None
        if heatname == "None":
            heatname = "Heat " + heatid

        heatclassid = str(heatobj.class_id)
        racechannels = self.getRaceChannels()
        thisheat = {
            "classid": heatclassid,
            "classname": "unsupported",
            "heatname": heatname,
            "heatid": heatid,
            "slots":[]
        }
        slots = db.slots_by_heat(heatid)
        
        for slot in slots:
            
            channel = racechannels[slot.node_index] 
            pilotcallsign = "-"
            if slot.pilot_id != 0:
                                    
                pilot = db.pilot_by_id(slot.pilot_id)
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
        if args["_eventName"] == "resync":
            classid = args["classid"]
        else:
            self.laptime_listener(args)
            savedracemeta = self._rhapi.db.race_by_id(args["race_id"])
            classid = savedracemeta.class_id
  
        raceclass = self._rhapi.db.raceclass_by_id(classid)
        classname = raceclass.name
        ranking = raceclass.ranking
        if self.isConnected() and self.isEnabled() and keys["notempty"]:

            rankpayload = []
            resultpayload = []

            if ranking != None:
                if isinstance(ranking, bool) and ranking is False:

                    rankpayload = []

                else:

                    meta = ranking["meta"]
                    method_label = meta["method_label"]
                    ranks = ranking["ranking"]
                    for rank in ranks:
                        pilot = {
                            "classid": classid,
                            "classname": classname,
                            "pilot_id": rank["pilot_id"],
                            "callsign": rank["callsign"],
                            "position": rank["position"],
                            "heat": rank["heat"],
                            "method_label": method_label

                        }
                        rankpayload.append(pilot)     

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
                        "method_label": primary_leaderboard
                    }
                    resultpayload.append(pilot)

                payload = {
                    "eventid": keys["eventid"],
                    "privatekey": keys["eventkey"],
                    "ranks": rankpayload,
                    "results": resultpayload
                }
                x = requests.post(self.CL_API_ENDPOINT+"/results", json = payload)
                self.logger.info("Results sent to cloud")

            else:
                self.logger.info("No results available to resync")

        else:
            self.logger.warning("No internet connection available")

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

    
