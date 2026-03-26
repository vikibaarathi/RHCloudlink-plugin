import logging
from eventmanager import Evt
from .cloudlink import CloudLink

def initialize(rhapi):
    cloudlink = CloudLink(rhapi)

    # Register the Flask blueprint early, before the app handles any requests
    try:
        from .registration_blueprint import create_registration_blueprint
        bp = create_registration_blueprint(rhapi)
        rhapi.ui.blueprint_add(bp)
    except Exception as e:
        logging.getLogger(__name__).error(f"CloudLink: failed to register blueprint: {e}")

    rhapi.events.on(Evt.STARTUP, cloudlink.init_plugin)
    rhapi.events.on(Evt.CLASS_ADD, cloudlink.class_listener, priority = 20)
    rhapi.events.on(Evt.CLASS_ALTER, cloudlink.class_listener,priority = 50)
    rhapi.events.on(Evt.HEAT_GENERATE, cloudlink.class_listener, priority = 99)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.heat_listener)
    rhapi.events.on(Evt.LAPS_SAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.LAPS_RESAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.HEAT_DELETE, cloudlink.class_heat_delete)
    rhapi.events.on(Evt.CLASS_DELETE, cloudlink.class_heat_delete)

