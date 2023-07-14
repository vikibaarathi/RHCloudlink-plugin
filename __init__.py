import logging
from eventmanager import Evt
from RHAPI import RHAPI
# from HeatGenerator import HeatGenerator, HeatPlan, HeatPlanSlot, SeedMethod
# from RHUI import UIField, UIFieldType, UIFieldSelectOption
import json
import socket


class CloudLink():
    def __init__(self,rhapi):
        self._rhapi = rhapi

    def register_handlers(self,args):
        self.mypilots()

    def mypilots(self):
        print("SYSTEM IS ONLINE") if self.isConnected() else print("SYSTEM IS OFFLINE")

        db = self._rhapi.db
        heats = db.heats
        slots = db.slots
        frequencysets = db.frequencysets
        defaultprofile = frequencysets[0]
        frequencies = defaultprofile.frequencies
        freq = json.loads(frequencies)
        bands = freq["b"]
        channels = freq["c"]
        print(bands)
        for heat in heats:
            print(heat.id)
            print("****")

        for slot in slots:
            id = slot.id
            heatid = slot.heat_id
            node = slot.node_index
            pilot = db.pilot_by_id(slot.pilot_id)
            pilotid = str(slot.pilot_id)
            
            freq = str(bands[node]) + str(channels[node])
            print("Heat:" + str(heatid) + "node: " + str(node) + "Frequency: " + freq + "pilot:" + pilotid)



    def getPilots(self):
        print("Getting Pilot")
        db = self._rhapi.db
        pilots = db.pilots
        for pilot in pilots:
            callsign = pilot.callsign
            print(callsign)

    def isConnected(self):
        try:
            s = socket.create_connection(
                ("www.geeksforgeeks.org", 80))
            if s is not None:
                s.close
            return True
        except OSError:
            pass
        return False




def initialize(rhapi):
    cloudlink = CloudLink(rhapi)
    rhapi.events.on(Evt.STARTUP, cloudlink.register_handlers)


