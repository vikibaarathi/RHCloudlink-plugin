import json
import requests
import logging
from sqlalchemy.ext.declarative import DeclarativeMeta
from RHUI import UIField, UIFieldType


class ClDataManager():


    def __init__(self,rhapi):
        self.logger = logging.getLogger(__name__)
        self._rhapi = rhapi

    def get_everything(self):

        data = {}
        #get pilots
        data["pilots"] = self.get_pilot_list()
        #get all classes
        data["classess"] = self.get_class_list()
        #get all heats
        data["heats"] = self.get_heat_list()
        data["frequencies"] = self.get_frequencies_list()
        data["slots"] = self.get_slot_list()
        #get ranking
        data["classranking"] = self.get_class_ranking()
        #get round results
        data["roundresults"] =  self.get_heat_round_results()
        #get class summary results
        data["classresults"] = self.get_class_results()
        #get all laps
        data["races"] = self.get_races_list()
        data["runs"] = self.get_races_pilot_run_list()
        data["laps"] = self.get_races_pilot_run_lap_list()
        jsondata = json.dumps(data)
        return jsondata



    def get_pilot_list(self):
        pilots = self._rhapi.db.pilots
        pilotlist = []
        for pilot in pilots:
            pilotobj = {
                "pilotid": pilot.id,
                "pilotcallsign": pilot.callsign
            }
            pilotlist.append(pilotobj)
        return pilotlist

    def get_class_list(self):

        clss = self._rhapi.db.raceclasses
        clslist = []
        for cls in clss:
            round_type = 0
            if hasattr(cls, "round_type"):
                round_type = cls.round_type
            clsobj = {
                "classid": cls.id,
                "classname": cls.name,
                "brackettype": "none",
                "round_type":round_type  

            }
            clslist.append(clsobj)

        return clslist
    
    def get_class_results(self):
        clss = self._rhapi.db.raceclasses
        overallresults = []
        for cls in clss:
            finalresults = []
            classid = cls.id
            classresults = self._rhapi.db.raceclass_results(classid)
            if classresults != None:
                meta = classresults["meta"]
                primary_leaderboard = meta["primary_leaderboard"]         
                filteredresults = classresults[primary_leaderboard]
                
                for result in filteredresults:

                    resultobj = {
                        "classid": classid,

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
                    finalresults.append(resultobj)

            thisclassresults = {
                "classid": classid,
                "classresults": finalresults
            }
            overallresults.append(thisclassresults)
        return overallresults
    
    def get_class_ranking(self):
        clss = self._rhapi.db.raceclasses
        overallresults = []
        for cls in clss:
            finalresults = []
            classid = cls.id
            classresults = self._rhapi.db.raceclass_ranking(classid)
            if classresults != None:
                if isinstance(classresults, bool) and classresults is False:
                    finalresults = []
                else:
                    meta = classresults["meta"]
                    primary_leaderboard = meta["method_label"]   
      
                    filteredresults = classresults["ranking"]
                    
                    for result in filteredresults:

                        resultobj = {
                            "classid": classid,
                            "pilot_id": result["pilot_id"],
                            "callsign": result["callsign"],
                            "position": result["position"],
                            "heat": result["heat"],
                            "method_label": primary_leaderboard
                        }
                        finalresults.append(resultobj)

            thisclassresults = {
                "classid": classid,
                "classresults": finalresults
            }
            overallresults.append(thisclassresults)
        return overallresults

    def get_heat_list(self):
        heats = self._rhapi.db.heats
        heatlist = []
        for heat in heats:
            #Set group ID
            group_id = 0
            if hasattr(heat, "group_id"):
                group_id = heat.group_id

            if heat.name == "None" or heat.name == "":
                heatname = "Heat "+ str(heat.id)
            else:
                heatname = heat.name    

            heatobj = {
                "heatid": heat.id,
                "heatname": heatname,
                "classid": heat.class_id,
                "group_id": group_id
            }
            heatlist.append(heatobj)
        return heatlist
    
    def get_slot_list(self):
        slots = self._rhapi.db.slots
        slotlist = []
        for slot in slots:
            slotobj = {
                "slotid": slot.id,
                "heatid": slot.heat_id,
                "nodeindex": slot.node_index,
                "pilotid": slot.pilot_id
            }
            slotlist.append(slotobj)
        return slotlist
    
    def get_frequencies_list(self):

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
    
    def get_races_list(self):
        races = self._rhapi.db.races
        allraces = []
        for race in races:
            raceobj = {
                "raceid": race.id,
                "roundid": race.round_id,
                "heatid": race.heat_id,
                "classid": race.class_id
            }

            allraces.append(raceobj)
        return allraces
    
    def get_races_pilot_run_list(self):
        pilotruns = self._rhapi.db.pilotruns
        allpilotruns = []
        for pilotrun in pilotruns:
            pilotrunobj = {
                "runid": pilotrun.id,
                "raceid": pilotrun.race_id,
                "nodeindex": pilotrun.node_index,
                "pilotid": pilotrun.pilot_id,
                "frequency": pilotrun.frequency

            }
            allpilotruns.append(pilotrunobj)

        return allpilotruns
    
    def get_races_pilot_run_lap_list(self):
        laps = self._rhapi.db.laps
        alllaps = []
        for lap in laps:
            lapobj = {
                "lapid": lap.id,
                "raceid": lap.race_id,
                "pilotraceid": lap.pilotrace_id,
                "nodeindex": lap.node_index,
                "pilotid": lap.pilot_id,
                "laptimeformatted": lap.lap_time_formatted,
                "deleted": lap.deleted
            }

            alllaps.append(lapobj)
        return alllaps
    
    def get_heat_round_results(self):
        races = self._rhapi.db.races
        overallresults = []
        for race in races:
            heatfinalresults = []
            raceid = race.id
            heatresults = self._rhapi.db.race_results(raceid)
            if heatresults != None:
                meta = heatresults["meta"]
                primary_leaderboard = meta["primary_leaderboard"]         
                filteredresults = heatresults[primary_leaderboard]
                
                for result in filteredresults:

                    resultobj = {
                        "raceid": raceid,
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
                    heatfinalresults.append(resultobj)
            thisheatresults = {
                "raceid": raceid,
                "classresults": heatfinalresults
            }
            overallresults.append(thisheatresults)
        return overallresults

