from eventmanager import Evt
from .constants import DEFAULT_API_ENDPOINT
from .api_client import CloudLinkAPIClient
from .cloudlink import CloudLink

def initialize(rhapi):
    try:
        from .config import CL_API_ENDPOINT
    except ImportError:
        CL_API_ENDPOINT = DEFAULT_API_ENDPOINT

    api_client = CloudLinkAPIClient(CL_API_ENDPOINT)
    cloudlink = CloudLink(rhapi, api_client)

    rhapi.events.on(Evt.STARTUP, cloudlink.init_plugin)
    rhapi.events.on(Evt.CLASS_ADD, cloudlink.class_listener, priority=20)
    rhapi.events.on(Evt.CLASS_ALTER, cloudlink.class_listener, priority=50)
    rhapi.events.on(Evt.HEAT_GENERATE, cloudlink.class_listener, priority=99)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.heat_listener)
    rhapi.events.on(Evt.LAPS_SAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.LAPS_RESAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.HEAT_DELETE, cloudlink.class_heat_delete)
    rhapi.events.on(Evt.CLASS_DELETE, cloudlink.class_heat_delete)
