import logging
from eventmanager import Evt
from .cloudlink import CloudLink
from .live_sync import LiveSync

def initialize(rhapi):
    cloudlink = CloudLink(rhapi)

    # Register the Flask blueprint for /cloudlink/* routes
    try:
        from .registration_blueprint import create_registration_blueprint
        bp = create_registration_blueprint(rhapi)
        try:
            rhapi.ui.blueprint_add(bp)
        except AssertionError:
            # Flask 3.x raises AssertionError if a request was already handled.
            # Temporarily clear the flag so the blueprint can still register.
            app = rhapi._racecontext.rhui._app
            app._got_first_request = False
            try:
                app.register_blueprint(bp)
            finally:
                app._got_first_request = True
            logging.getLogger(__name__).info("CloudLink: blueprint registered (late)")
    except Exception as e:
        logging.getLogger(__name__).error(f"CloudLink: failed to register blueprint: {e}")

    # --- Existing sync (finalized results, source of truth) ---
    rhapi.events.on(Evt.STARTUP, cloudlink.init_plugin)
    rhapi.events.on(Evt.CLASS_ADD, cloudlink.class_listener, priority = 20)
    rhapi.events.on(Evt.CLASS_ALTER, cloudlink.class_listener, priority = 50)
    rhapi.events.on(Evt.HEAT_GENERATE, cloudlink.class_listener, priority = 99)
    rhapi.events.on(Evt.HEAT_ALTER, cloudlink.heat_listener)
    rhapi.events.on(Evt.LAPS_SAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.LAPS_RESAVE, cloudlink.results_listener)
    rhapi.events.on(Evt.HEAT_DELETE, cloudlink.class_heat_delete)
    rhapi.events.on(Evt.CLASS_DELETE, cloudlink.class_heat_delete)

    # --- Live sync (real-time lap streaming during active races) ---
    # Priority >= 200 ensures these run in gevent greenlets so they never
    # block the timing engine's critical path.
    def is_live_sync_ready():
        """Live sync requires the plugin to be connected, enabled, AND the live toggle on."""
        if not (cloudlink.isConnected() and cloudlink.isEnabled()):
            return False
        return rhapi.db.option("cl-live-sync") == "1"

    live_sync = LiveSync(
        rhapi=rhapi,
        get_keys_fn=cloudlink.getEventKeys,
        is_ready_fn=is_live_sync_ready,
        api_endpoint=cloudlink.CL_API_ENDPOINT,
    )

    rhapi.events.on(Evt.HEAT_SET, live_sync.on_heat_set, priority=200)
    rhapi.events.on(Evt.RACE_START, live_sync.on_race_start, priority=200)
    rhapi.events.on(Evt.RACE_LAP_RECORDED, live_sync.on_lap_recorded, priority=200)
    rhapi.events.on(Evt.RACE_STOP, live_sync.on_race_stop, priority=200)

