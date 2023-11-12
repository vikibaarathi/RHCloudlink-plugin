# RHCLOUDLINK USER GUIDE

## Installation 

This plugin expands the capabilities of RotorHazard FPV Timing System by publish race information to a cloud platform. The following are the setup steps. 

### STEP 1

Be sure to create an event at https://rhcloudlink.com/register. Be sure to keep the event ID and the private key safely. The private key is meant to be used by the Race Director alone. 

### STEP 2

Head over to the [releases page](https://github.com/vikibaarathi/RHCloudlink-plugin/releases) and download the latest plugin zip. Unzip the folder, copy the entire folder into the `/src/server/plugins` folder within RotorHazard followed by a restart of the timer. Details of how plugins work within RotorHazard are described at the [RotorHazard Plugins](https://github.com/RotorHazard/RotorHazard/blob/v4.0.0/doc/Plugins.md) page.

### STEP 3
Once reboot is complete, the startup logs will indiciate if the plugin was successfully initiated. Heading over to the settings page, there will be a new section called "Cloudlink" at the bottom of the page. Key in the the event ID and private key from step 1 and check the enable plugin box. For first time setup, the resync button does not need to be pressed. 

Thats it! We are all set. Creating new classes, new heats, seeding pilots, saving races or marshalling races will automatically trigger the plugin to send data to the cloud. 

Take note, the plugin disables itself if:
* No active internet connection is available.
* Event ID or Private Key is missing.
* If a notification pops up indicating a mandatory plugin update is required.

## Usage 

The cloudlink plugin aims to give race directors a seemless or frictionless experience when running tournaments. The following are trigger points for when data is pushed to the cloud.

### Classes

Cloudlink uses classess to divide the cloud experience. Navigation on rhcloudlink.com allows users to switch between classes. Classes are pushed to the cloud:

* Manual class creation.
* Generated class creation.
* Class name rename.
* Cloudlink settings page resync function. 

### Heats

Heats hold the pilot callsign and race channel and grouped by their classes. Unclassified heats are not pushed to the cloud. Heats freshly created or generated are not sent to cloud immediately. Pilots must be assigned for the trigger to happen. They following triggers the heat sync:

* Renaming the heat name.
* Selecting a pilot over a channel in a heat.
* Using the auto frequency functionality. 
* Cloudlink settings page resync function. 

