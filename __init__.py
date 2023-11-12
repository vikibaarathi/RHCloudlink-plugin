from eventmanager import Evt
from RHAPI import RHAPI
import json
import socket
import requests
import logging
from RHUI import UIField, UIFieldType, UIFieldSelectOption
logger = logging.getLogger(__name__)
class CloudLink():
    CL_VERSION = "0.1.0"
    CL_API_ENDPOINT = "https://api.rhcloudlink.com"
    CL_DEFAULT_PROFILE = 0
    CL_FORCEUPDATE = False

    def __init__(self,rhapi):
        self._rhapi = rhapi
        
    def initialize_plugin(self,args):
        
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            x = requests.get(self.CL_API_ENDPOINT+'/healthcheck')
            respond = x.json()
            if self.CL_VERSION != respond["version"]:
                if respond["softupgrade"] == True:
                    logger.warning("New version of Cloud Link is available. Please consider upgrading.")
    

                if respond["forceupgrade"] == True:
                    logger.warning("Cloudlink plugin needs to bee updated. ")
                    self.CL_FORCEUPDATE = True
            logger.info("Cloud-Link plugin ready to go.")
        else:
            logger.warning("No internet connection available")
        
        self.init_ui(args)
        
    def init_ui(self,args):
        ui = self._rhapi.ui
        fields = self._rhapi.fields
        #Register the panel for Cloud Link
        ui.register_panel("cloud-link", "Cloud Link", "settings")
        
        #Register all the text input for Cloud Link
        cl_enableplugin = UIField(name = 'cl-enable-plugin', label = 'Enable Cloud Link Plugin', field_type = UIFieldType.CHECKBOX, desc = "Enable or disable this plugin. Unchecking this box will stop all communication with the Cloud Link server.")
        fields.register_option(cl_enableplugin, "cloud-link")
        cl_eventid = UIField(name = 'cl-event-id', label = 'Cloud Link Event ID', field_type = UIFieldType.TEXT, desc = "Event must be registered at cloudlink.com")
        cl_eventkey = UIField(name = 'cl-event-key', label = 'Cloud Link Event Private Key', field_type = UIFieldType.TEXT, desc = "Authentication key provided by Cloud Link during event registration.")

        fields.register_option(cl_eventid, "cloud-link")
        fields.register_option(cl_eventkey, "cloud-link")


        ui.register_quickbutton("cloud-link", "send-all-button", "clear and re-sync", self.ui_button)

    def ui_button(self,args):
        ui = self._rhapi.ui
        ui.message_notify("Initializing resyncronization protocol...")
        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"]         
            }

            try:
                x = requests.delete(self.CL_API_ENDPOINT+"/event", json = payload)
                x.raise_for_status()
                response = x.json()

                if response == "All records removed":
                    print(response)
                    self.resend_everything()

            except Exception as err:
                print(f'Other error occurred: {err}')

    def resend_everything(self):

        ui = self._rhapi.ui

        #GET ALL CLASSES
        db = self._rhapi.db
        classes = db.raceclasses

        total = len(classes)
        for idx, clss in enumerate(classes):
            
            #GET 1 CLASS
            classid = clss.id
            classname = clss.name
            #check class name if blank
            args = {
                "_eventName": "resync",
                "classid": classid,
                "classname": classname
            }
            print(args)
            self.class_listener(args)

            #GET ALL HEATS FROM THIS CLASS
            heats = db.heats_by_class(classid)

            for heat in heats:
                args = {
                    "_eventName": "resync",
                    "heat_id": heat.id
                }

                print(args)
                self.heat_listener(args)

            #GET RESULTS FOR THIS CLASS
            resultargs = {
                "_eventName": "resync",
                "classid": classid
            }
            self.results_listener(resultargs)
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
                brackettype = "none"

            elif eventname == "heatGenerate":
                classid = args["output_class_id"]
                raceclass = self._rhapi.db.raceclass_by_id(classid)
                if raceclass.name == "":
                    classname = "Class " + str(classid)
                else:
                    classname = raceclass.name
                brackettype = args["generator"]

            elif eventname == "resync":
                classid = args["classid"]
                classname = args["classname"]
                brackettype = "none" 
                #ENHANCE TO REMEMBER BRACKET TYPE

            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"],
                "classid": classid,
                "classname": classname,
                "brackettype": brackettype         
            }

            x = requests.post(self.CL_API_ENDPOINT+"/class", json = payload)
        else:
            logger.warning("Cloud-Link Disabled")

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

            # results = json.dumps(payload)
            # logger.warning(results)
            x = requests.post(self.CL_API_ENDPOINT+"/slots", json = payload)
        else:
            logger.warning("Cloud-Link Disabled")

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
            pilotcallsign = "empty"
            if slot.pilot_id != 0:                  
                pilot = db.pilot_by_id(slot.pilot_id)
                pilotcallsign = pilot.callsign


            thisslot = {
                "nodeindex": slot.node_index,
                "channel": channel,
                "callsign": pilotcallsign
            }
            thisheat["slots"].append(thisslot)
        return thisheat

    def getRaceChannels(self):
        db = self._rhapi.db
        frequencysets = db.frequencysets
        defaultprofile = frequencysets[self.CL_DEFAULT_PROFILE]
        frequencies = defaultprofile.frequencies
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

    def results_listener(self,args):
        keys = self.getEventKeys()

        if args["_eventName"] == "resync":
            classid = args["classid"]
        else:
            savedracemeta = self._rhapi.db.race_by_id(args["race_id"])
            classid = savedracemeta.class_id
  
        raceclass = self._rhapi.db.raceclass_by_id(classid)
        print(raceclass)
        classname = raceclass.name
        ranking = raceclass.ranking
        print(ranking)
        if self.isConnected() and self.isEnabled() and keys["notempty"]:

            rankpayload = []
            resultpayload = []

            if ranking != None and ranking is True:
                print("send ranking")
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

            print("send results")
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

                # results = json.dumps(payload)
                # logger.warning(results)
                #send to cloud
                x = requests.post(self.CL_API_ENDPOINT+"/results", json = payload)
                logger.info("Results sent to cloud")

        else:
            logger.warning("No internet connection available")

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
                logger.warning("Cloudlink requires a mandatory update. Please update and restart the timer. No results will be synced for now.")
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

def initialize(rhapi):
    cloudlink = CloudLink(rhapi)
    rhapi.events.on(Evt.STARTUP, cloudlink.initialize_plugin)
    rhapi.events.on(Evt.CLASS_ADD, cloudlink.class_listener)
    rhapi.events.on(Evt.CLASS_ALTER, cloudlink.class_listener)
    rhapi.events.on(Evt.HEAT_GENERATE, cloudlink.class_listener)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.heat_listener)
    rhapi.events.on(Evt.LAPS_SAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.LAPS_RESAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.HEAT_DELETE, cloudlink.class_heat_delete)
    rhapi.events.on(Evt.CLASS_DELETE, cloudlink.class_heat_delete)


    
