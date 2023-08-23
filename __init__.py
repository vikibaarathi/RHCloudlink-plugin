from eventmanager import Evt
from RHAPI import RHAPI
import json
import socket
import requests

class CloudLink():

    CL_ENDPOINT = "www.google.com"
    CL_API_ENDPOINT = "https://bgj3xgowu8.execute-api.ap-southeast-1.amazonaws.com/prod/slots"
    CL_QUALIFYING_CLASS_ID = 1
    CL_DEFAULT_PROFILE = 0

    def __init__(self,rhapi):
        self._rhapi = rhapi

    def register_handlers(self,args):
        self.getGrouping()

    def send_individual_heat(self,args):
        self.getSingleGroup(args)

    def send_qualifying_results(self,args):
        print("Race Saved")
        db = self._rhapi.db
        fullresults = db.raceclass_results(1)
        #print(fullresults)
        threeconst = fullresults["by_consecutives"]
        #print(threeconst)
        for rank in threeconst:
            pilot = {
                "pilot_id": rank["pilot_id"],
                "callsign": rank["callsign"],
                "position": rank["position"],
                "consecutives": rank["consecutives"],
                "consecutives_base" : rank["consecutives_base"]
            }
            print(pilot)

       
        

    def getSingleGroup(self,args):
        print("SYSTEM IS ONLINE") if self.isConnected() else print("SYSTEM IS OFFLINE")
        db = self._rhapi.db
        heat = db.heat_by_id(args["heat_id"])

        groups = []

        thisheat = self.getGroupingDetails(heat,db)
        groups.append(thisheat)

        payload = {
            "eventid":"vk005",
            "privatekey": "8454122",
            "heats": groups
        }

        results = json.dumps(payload)
        x = requests.post(self.CL_API_ENDPOINT, json = payload)
        # print(x.text)

        # print(results)

    def getGrouping(self):
        print("SYSTEM IS ONLINE") if self.isConnected() else print("SYSTEM IS OFFLINE")
        db = self._rhapi.db
        heatsinclass = db.heats_by_class(self.CL_QUALIFYING_CLASS_ID)

        groups = []
        for heat in heatsinclass:
            thisheat = self.getGroupingDetails(heat,db)
            groups.append(thisheat)



        payload = {
            "eventid":"vk001",
            "privatekey": "8454122",
            "heats": groups
        }

        results = json.dumps(payload)
        print(results)

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

def initialize(rhapi):
    cloudlink = CloudLink(rhapi)
    rhapi.events.on(Evt.STARTUP, cloudlink.register_handlers)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.send_individual_heat)
    rhapi.events.on(Evt.LAPS_SAVE, cloudlink.send_qualifying_results)
    rhapi.events.on(Evt.LAPS_RESAVE, cloudlink.send_qualifying_results)
    

