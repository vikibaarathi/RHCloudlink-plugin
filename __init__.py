from eventmanager import Evt
from RHAPI import RHAPI
import json
import socket

class CloudLink():

    CL_ENDPOINT = "www.google.com"
    CL_QUALIFYING_CLASS_ID = 1
    CL_DEFAULT_PROFILE = 0

    def __init__(self,rhapi):
        self._rhapi = rhapi

    def register_handlers(self,args):
        #self.mypilots()
        self.getGrouping()

    def getGrouping(self):
        print("SYSTEM IS ONLINE") if self.isConnected() else print("SYSTEM IS OFFLINE")
        db = self._rhapi.db
        heatsinclass = db.heats_by_class(self.CL_QUALIFYING_CLASS_ID)

        racechannels = self.getRaceChannels()

        groups = []
        for heat in heatsinclass:
            heatname = str(heat.name)
            heatid = str(heat.id)
            thisheat = {
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

            groups.append(thisheat)

        print(groups)

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

