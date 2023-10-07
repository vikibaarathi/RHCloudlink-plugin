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
    CL_API_ENDPOINT = "https://bgj3xgowu8.execute-api.ap-southeast-1.amazonaws.com/prod/slots"
    CL_API_ENDPOINT_RESULTS = "https://bgj3xgowu8.execute-api.ap-southeast-1.amazonaws.com/prod/results"
    CL_EVENT_ID = 'PH2405'
    CL_QUALIFYING_CLASS_ID = 1
    CL_DOUBLE_ELIM_CLASS_ID = 2
    CL_DEFAULT_PROFILE = 0

    def __init__(self,rhapi):
        self._rhapi = rhapi

    def listen_generator(self,args):
        print(args)

    def register_handlers(self,args):
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


        ui.register_quickbutton("cloud-link", "send-all-button", "Sync All", self.ui_button)
        ui.register_quickbutton("cloud-link", "remove-all-button", "Remove All", self.ui_button)



    def ui_button(self,args):
        print("Hello World")

    def send_individual_heat(self,args):

        keys = self.getEventKeys()

        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            print("Sending heat to cloud")
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
            x = requests.post(self.CL_API_ENDPOINT, json = payload)
        else:
            print("Cloud-Link Disabled")

    def send_qualifying_results(self,args):
        keys = self.getEventKeys()
        raceid = args["race_id"]
        savedracemeta = self._rhapi.db.race_by_id(raceid)
        classid = savedracemeta.class_id
        raceclass = self._rhapi.db.raceclass_by_id(classid)
        classname = raceclass.name
        ranking = raceclass.ranking

        if self.isConnected() and self.isEnabled() and keys["notempty"]:
            print("Sending results to cloud")
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

            results = json.dumps(payload)
            print(results)
            #send to cloud
            x = requests.post(self.CL_API_ENDPOINT_RESULTS, json = payload)
            print("Results sent to cloud")

        else:
            print("No internet connection available")

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
    rhapi.events.on(Evt.STARTUP, cloudlink.register_handlers)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.send_individual_heat)
    rhapi.events.on(Evt.LAPS_SAVE, cloudlink.send_qualifying_results)
    rhapi.events.on(Evt.LAPS_RESAVE, cloudlink.send_qualifying_results)
    rhapi.events.on(Evt.HEAT_GENERATE, cloudlink.listen_generator)
