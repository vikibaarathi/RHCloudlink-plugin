from eventmanager import Evt
from RHAPI import RHAPI
import json
import socket
import requests
import logging
import RHUtils
from RHUI import UIField, UIFieldType, UIFieldSelectOption

class CloudLink():

    CL_ENDPOINT = "www.google.com"
    CL_API_ENDPOINT = "https://bgj3xgowu8.execute-api.ap-southeast-1.amazonaws.com/prod"
    CL_DEFAULT_PROFILE = 0

    def __init__(self,rhapi):
        self._rhapi = rhapi
        
    def initialize_plugin(self,args):
        print("Cloud-Link plugin ready to go.")
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

    def class_listener(self,args):

        keys = self.getEventKeys()
        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            
            eventname = args["_eventName"]
            if eventname == "classAdd":
                classid = args["class_id"]
                classname = str(classid)
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
                    classname = str(classid)
                else:
                    classname = raceclass.name
                brackettype = args["generator"]         

            payload = {
                "eventid": keys["eventid"],
                "privatekey": keys["eventkey"],
                "classid": classid,
                "classname": classname,
                "brackettype": brackettype         
            }

            x = requests.post(self.CL_API_ENDPOINT+"/class", json = payload)
        else:
            print("Cloud-Link Disabled")

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
            # print(results)
            x = requests.post(self.CL_API_ENDPOINT+"/slots", json = payload)
        else:
            print("Cloud-Link Disabled")

    def getGroupingDetails(self, heatobj, db):
        heatname = str(heatobj.name)
        heatid = str(heatobj.id)
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
        savedracemeta = self._rhapi.db.race_by_id(args["race_id"])
        classid = savedracemeta.class_id
        raceclass = self._rhapi.db.raceclass_by_id(classid)
        classname = raceclass.name
        ranking = raceclass.ranking

        if self.isConnected() and self.isEnabled() and keys["notempty"]:

            rankpayload = []
            resultpayload = []

            if ranking:
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
            # print(results)
            #send to cloud
            x = requests.post(self.CL_API_ENDPOINT+"/results", json = payload)
            print("Results sent to cloud")

        else:
            print("No internet connection available")

    def isConnected(self):
        try:
            s = socket.create_connection(
                (self.CL_ENDPOINT, 80))
            if s is not None:
                s.close
            return True
        except OSError:
            pass
        return False
    
    def isEnabled(self):
        enabled = self._rhapi.db.option("cl-enable-plugin")
        
        print(enabled)
        if enabled == "1":
            return True
        else:
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


    
