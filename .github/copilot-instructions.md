# RHCloudlink Plugin Development Guide

## Architecture Overview

This is a **RotorHazard FPV Timing System plugin** that syncs race data to rhcloudlink.com cloud platform in real-time. The plugin follows RotorHazard's event-driven architecture using the `rhapi` interface.

### Core Components

- **`__init__.py`**: Plugin entry point that registers event listeners for RotorHazard events (CLASS_ADD, HEAT_ALTER, LAPS_SAVE, etc.)
- **`cloudlink.py`**: Main CloudLink class handling API communication and event processing
- **`datamanager.py`**: ClDataManager class for data aggregation and serialization
- **`manifest.json`**: Plugin metadata (version 1.3.0, requires rhapi 1.2+)

### Event-Driven Pattern

The plugin registers listeners for specific RotorHazard events with different priorities:
```python
rhapi.events.on(Evt.CLASS_ADD, cloudlink.class_listener, priority=20)
rhapi.events.on(Evt.HEAT_ALTER, cloudlink.heat_listener)
rhapi.events.on(Evt.LAPS_SAVE, cloudlink.results_listener)
```

## Key Development Patterns

### API Communication

All cloud communication uses `self.CL_API_ENDPOINT` with consistent payload structure:
```python
payload = {
    "eventid": keys["eventid"],
    "privatekey": keys["eventkey"],
    # ... specific data
}
requests.post(f"{self.CL_API_ENDPOINT}/{endpoint}", json=payload)
```

### State Validation

Every operation checks three conditions before proceeding:
```python
if self.isConnected() and self.isEnabled() and keys["notempty"]:
    # Process request
else:
    self.logger.warning("Cloud-Link Disabled")
```

### Data Transformation

The plugin transforms RotorHazard database objects into cloud-compatible JSON. Key patterns:
- **Classes**: Include `round_type` for bracket generation detection
- **Heats**: Group slots by heat with pilot callsigns and node channels  
- **Results**: Separate ranking vs leaderboard data with fastest/consecutive lap sources

### UI Integration

Uses RotorHazard's RHUI framework for the Format page configuration:
- Panel: "cloud-link" in "format" section
- Fields: enable checkbox, event ID, private key
- Quick button: "Resync" for manual synchronization

## Critical Workflows

### Plugin Installation
1. Copy `cloudlink/` to RotorHazard plugins directory
2. Restart RotorHazard
3. Configure on Format page with rhcloudlink.com credentials
4. Plugin auto-validates connection and version compatibility

### Resync Operation
The resync functionality (`resync_new()`) sends complete race state via `/resync` endpoint using `ClDataManager.get_everything()` which aggregates all classes, heats, pilots, frequencies, slots, rankings, and race results.

### Version Management
Plugin checks for version compatibility on startup against `CL_API_ENDPOINT/healthcheck`, setting `CL_FORCEUPDATE` flag if mandatory upgrade required.

## Testing & Validation

- **RHFest validation**: Automated via GitHub Actions using `ghcr.io/rotorhazard/rhfest-action:v2`
- **Branch strategy**: Feature branches for specific issues (e.g., `58-pushing-results-with-zero-laps`)
- **Current branch**: `support-multiple-ranking` indicates active development on ranking system enhancements

## Integration Points

- **RotorHazard Database**: Accesses via `self._rhapi.db` for pilots, classes, heats, results
- **RotorHazard Events**: Listens to lifecycle events for real-time synchronization
- **Cloud API**: RESTful endpoints for classes, slots, results, resync operations
- **UI Framework**: Uses RHUI for seamless integration with RotorHazard's web interface

## Common Gotchas

- Plugin disables itself if internet unavailable, credentials missing, or force update required
- Heat data only syncs when pilots are assigned (empty heats ignored)
- Bracket type detection relies on generator names and args structure
- Results include both ranking (tournament progression) and leaderboard (final standings) data
- Version compatibility strictly enforced via healthcheck API