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
* Event date of that particular event ID has been passed. 

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

### Generators

Generators are the best way to efficiiently manage a race. Generated classes are automatically pushed to the cloud, while heats wait for pilots to be assigned or seeded. Double Elimination and Single Elimination generators automatically tell Cloudlink to draw out brackets to give racers and spectators a better exprience in enjoying the race. 

### Results & Ranking

Saving a race will automatically push results to the cloud. Likewise, when the RotorHazard marshalling page is used, results get resent again. This keeps racers and spectators update to date with tournament progress. 

Cloudlink also is able to tell if a ranking system is being used. Ranking results will be displayed as a seperate table on rhcloudlink.com.

### Resync Function

The plugin Cloudlink section in the settings page of RotorHazard, allows race director to resync all classes, heats and results to the cloud. This is a one way up system. Nothing is updated in RotorHazard by the plugin. If this functionality is used, please be patient while RotorHazard empties the cloud database and resends everything. The time it takes will depend on the size of the race. 

* Use if for some reason internet was interrupted mid tournament.
* Race Director forgets to enable the plugin before a race.