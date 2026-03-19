from eventmanager import Evt
from .cloudlink import CloudLink

def initialize(rhapi):
    cloudlink = CloudLink(rhapi)
    rhapi.events.on(Evt.STARTUP, cloudlink.init_plugin)
    rhapi.events.on(Evt.CLASS_ADD, cloudlink.class_listener, priority = 20)
    rhapi.events.on(Evt.CLASS_ALTER, cloudlink.class_listener,priority = 50)
    rhapi.events.on(Evt.HEAT_GENERATE, cloudlink.class_listener, priority = 99)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.heat_listener)
    rhapi.events.on(Evt.LAPS_SAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.LAPS_RESAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.HEAT_DELETE, cloudlink.class_heat_delete)
    rhapi.events.on(Evt.CLASS_DELETE, cloudlink.class_heat_delete)

    # Live telemetry hooks
    rhapi.events.on(Evt.RACE_STAGE, cloudlink.live_race_stage)
    rhapi.events.on(Evt.RACE_START, cloudlink.live_race_start)
    rhapi.events.on(Evt.RACE_FINISH, cloudlink.live_race_finish)
    rhapi.events.on(Evt.HEAT_SET, cloudlink.live_heat_set)
    rhapi.events.on(Evt.LAP_RECORDED, cloudlink.live_lap_recorded)

