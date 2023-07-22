from eventmanager import Evt
from RHAPI import RHAPI
import json
import socket

class CloudLink():

    CL_DEFAULT_PROFILE = 0
    CL_EVENT_ID = "VK091233"

    def __init__(self,rhapi):
        self._rhapi = rhapi

    def send_individual_heat(self,args):
        db = self._rhapi.db
        heat = db.heat_by_id(args["heat_id"])

        groups = []

        thisheat = self.getGroupingDetails(heat,db)
        groups.append(thisheat)

        results = json.dumps(groups)
        #Final payload
        print(results)

    def getGroupingDetails(self, heatobj, db):
        heatname = str(heatobj.name)
        heatid = str(heatobj.id)
        heatclassid = str(heatobj.class_id)
        racechannels = self.getRaceChannels()

        thisheat = {
            "eventid": self.CL_EVENT_ID,
            "classid": heatclassid,
            "heatid": heatid,
            "heatname": heatname,
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

def initialize(rhapi):
    cloudlink = CloudLink(rhapi)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.send_individual_heat)

