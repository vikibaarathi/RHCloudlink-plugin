import json
import logging
from .payloads import build_result_entry, format_heat_name


class ClDataManager():

    def __init__(self, rhapi):
        self.logger = logging.getLogger(__name__)
        self._rhapi = rhapi

    def get_everything(self):
        data = {}
        data["pilots"] = self.get_pilot_list()
        data["classess"] = self.get_class_list()
        data["heats"] = self.get_heat_list()
        data["frequencies"] = self.get_frequencies_list()
        data["slots"] = self.get_slot_list()
        data["classranking"] = self.get_class_ranking()
        data["classrankingv2"] = self.get_class_ranking_v2()
        data["roundresults"] = self.get_heat_round_results()
        data["classresults"] = self.get_class_results()
        data["races"] = self.get_races_list()
        data["runs"] = self.get_races_pilot_run_list()
        data["laps"] = self.get_races_pilot_run_lap_list()
        jsondata = json.dumps(data)
        return jsondata

    def get_pilot_list(self):
        pilots = self._rhapi.db.pilots
        return [{"pilotid": p.id, "pilotcallsign": p.callsign} for p in pilots]

    def get_class_list(self):
        clss = self._rhapi.db.raceclasses
        clslist = []
        for cls in clss:
            round_type = 0
            if hasattr(cls, "round_type"):
                round_type = cls.round_type
            clslist.append({
                "classid": cls.id,
                "classname": cls.name,
                "brackettype": "none",
                "round_type": round_type,
            })
        return clslist

    def get_class_results(self):
        clss = self._rhapi.db.raceclasses
        overallresults = []
        for cls in clss:
            classid = cls.id
            classresults = self._rhapi.db.raceclass_results(classid)
            finalresults = []
            if classresults is not None:
                meta = classresults["meta"]
                primary_leaderboard = meta["primary_leaderboard"]
                filteredresults = classresults[primary_leaderboard]
                finalresults = [
                    build_result_entry(classid, None, result, primary_leaderboard)
                    for result in filteredresults
                ]
            overallresults.append({
                "classid": classid,
                "classresults": finalresults,
            })
        return overallresults

    def get_class_ranking(self):
        # Legacy ranking method - currently disabled to avoid conflicts with classrankingv2
        return []

    def get_class_ranking_v2(self):
        clss = self._rhapi.db.raceclasses
        overallresults = []
        for cls in clss:
            classid = cls.id
            classresults = self._rhapi.db.raceclass_ranking(classid)
            ranking_data = classresults if (classresults is not None and classresults is not False) else {}
            overallresults.append({
                "classid": classid,
                "ranking": ranking_data,
            })
        return overallresults

    def get_heat_list(self):
        heats = self._rhapi.db.heats
        heatlist = []
        for heat in heats:
            group_id = 0
            if hasattr(heat, "group_id"):
                group_id = heat.group_id
            heatname = format_heat_name(heat.name, heat.id)
            heatlist.append({
                "heatid": heat.id,
                "heatname": heatname,
                "classid": heat.class_id,
                "group_id": group_id,
            })
        return heatlist

    def get_slot_list(self):
        slots = self._rhapi.db.slots
        return [{
            "slotid": s.id,
            "heatid": s.heat_id,
            "nodeindex": s.node_index,
            "pilotid": s.pilot_id,
        } for s in slots]

    def get_frequencies_list(self):
        frequencies = self._rhapi.race.frequencyset.frequencies
        freq = json.loads(frequencies)
        bands = freq["b"]
        channels = freq["c"]
        racechannels = []
        for i, band in enumerate(bands):
            if str(band) == 'None':
                racechannels.insert(i, "0")
            else:
                racechannels.insert(i, str(band) + str(channels[i]))
        return racechannels

    def get_races_list(self):
        races = self._rhapi.db.races
        return [{
            "raceid": r.id,
            "roundid": r.round_id,
            "heatid": r.heat_id,
            "classid": r.class_id,
        } for r in races]

    def get_races_pilot_run_list(self):
        pilotruns = self._rhapi.db.pilotruns
        return [{
            "runid": pr.id,
            "raceid": pr.race_id,
            "nodeindex": pr.node_index,
            "pilotid": pr.pilot_id,
            "frequency": pr.frequency,
        } for pr in pilotruns]

    def get_races_pilot_run_lap_list(self):
        laps = self._rhapi.db.laps
        return [{
            "lapid": lap.id,
            "raceid": lap.race_id,
            "pilotraceid": lap.pilotrace_id,
            "nodeindex": lap.node_index,
            "pilotid": lap.pilot_id,
            "laptimeformatted": lap.lap_time_formatted,
            "deleted": lap.deleted,
        } for lap in laps]

    def get_heat_round_results(self):
        races = self._rhapi.db.races
        overallresults = []
        for race in races:
            raceid = race.id
            heatresults = self._rhapi.db.race_results(raceid)
            heatfinalresults = []
            if heatresults is not None:
                meta = heatresults["meta"]
                primary_leaderboard = meta["primary_leaderboard"]
                filteredresults = heatresults[primary_leaderboard]
                for result in filteredresults:
                    heatfinalresults.append({
                        "raceid": raceid,
                        "pilot_id": result["pilot_id"],
                        "callsign": result["callsign"],
                        "position": result["position"],
                        "consecutives": result["consecutives"],
                        "consecutives_base": result["consecutives_base"],
                        "laps": result["laps"],
                        "total_time": result["total_time"],
                        "average_lap": result["average_lap"],
                        "fastest_lap": result["fastest_lap"],
                        "method_label": primary_leaderboard,
                    })
            overallresults.append({
                "raceid": raceid,
                "classresults": heatfinalresults,
            })
        return overallresults
