# RHCLOUDLINK USER GUIDE

## 1.0 Installation 

This plugin expands the capabilities of the RotorHazard FPV Timing System by publishing race information to a cloud platform. The following are the setup steps. 

### STEP 1

Create an event at https://rhcloudlink.com/register. Be sure to keep the event ID and the private key safely. The private key is meant to be used only by the Race Director alone. 

### STEP 2

Head over to the [releases page](https://github.com/vikibaarathi/RHCloudlink-plugin/releases) and download the latest plugin zip. 

Unzip the folder and rename the folder to `rhcloudlink`. 

Copy the entire folder into the `/src/server/plugins` folder within RotorHazard followed by a restart of the timer.

### STEP 3
![Screenshot 2024-04-11 at 9 13 34 PM](https://github.com/vikibaarathi/RHCloudlink-plugin/assets/17153870/2e45eeaa-b3b9-4ed6-9fa7-2c6738c587db)

Once reboot is complete, the startup logs will indiciate if the plugin was successfully initiated. Heading over to the Format page, there will be a new section called "Cloudlink" at the bottom of the page. Key in the the event ID and private key from step 1 and check the enable plugin box. 

For first time setup, the resync button does not need to be pressed. 

Thats it! You are all set. Creating new classes, new heats, seeding pilots, saving races or marshalling races will automatically trigger the plugin to send data to the cloud. 

Take note, the plugin disables itself if:
* No active internet connection is available.
* Event ID or Private Key is missing.
* If a notification pops up indicating a mandatory plugin update is required.

## 2.0 Usage 

The cloudlink plugin aims to give race directors a seemless or frictionless experience when running tournaments. The following are trigger points for when data is pushed to the cloud.

### Classes

Cloudlink uses classess to divide the cloud experience. This means a new navigation link and page will be created automatically for each class created in RotorHazard. Classes are pushed to the cloud when:

* Classes are created manually.
* Classes are generated using Generators.
* Classes are renamed.
* Resync button pressed in Format page. 

### Heats

Heats hold the pilot callsign and race channel and grouped by their classes. Unclassified heats are not pushed to the cloud. Heats freshly created or Generated are not sent to cloud immediately. Pilots must be assigned for the trigger to happen. They following triggers are the trigger points:

* Heats are renamed
* Assigning a pilot to a channel
* Using the auto frequency functionality. 
* Resync button pressed in settings page. 

### Generators

Generators are the best way to efficiiently manage a race. Generated classes are automatically pushed to the cloud, while heats wait for pilots to be assigned or seeded. 

Double Elimination and Single Elimination generators automatically tell Cloudlink to draw out brackets to give racers and spectators a better exprience in enjoying the race. 

### Results & Ranking

Saving a race will automatically push results to the cloud. Likewise, when the RotorHazard marshalling page is used, results get resent again. This keeps racers and spectators updated with tournament progress. 

Cloudlink is also able to tell if a ranking system is being used. Ranking results will be displayed as a seperate table on rhcloudlink.com.

### Resync Function

The plugin "Cloudlink" section in the Format page of RotorHazard, allows race director to resync all classes, heats and results to the cloud. This is a one way up system. Nothing is updated in RotorHazard by the plugin. If this functionality is used, please be patient while RotorHazard empties the cloud database and resends everything. The time it takes will depend on the size of the race. 

* Use if for some reason internet was interrupted mid tournament.
* Race Director forgets to enable the plugin before a race.

## Advanced features

More advanced features will be rolled out periodically such as analytics, push notification, race director admin page, etc. Stay tune for more updates. 
