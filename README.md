# Mylar Standalone Sensor and Upcoming Media Component

Home Assistant component to feed [Upcoming Media Card](https://github.com/custom-cards/upcoming-media-card) with
Mylar's upcoming comics and recent activity.</br>

### If you're having issues, check out the [troubleshooting guide](https://github.com/custom-cards/upcoming-media-card/blob/master/troubleshooting.md) before posting an issue or asking for help on the forums.

## Installation:

1. Install this component by copying [these files](https://github.com/DarkSir23/sensor.mylar/tree/master) to `/custom_components/mylar/`.
2. (Optional) Install the card: [Upcoming Media Card](https://github.com/custom-cards/upcoming-media-card)
3. Add the code to your `configuration.yaml` using the config options below.
4. Add the code for the card to your `ui-lovelace.yaml`. 
5. **You will need to restart after installation for the component to start working.**

| key | default | required | description
| --- | --- | --- | ---
| api_key | | yes | Your Mylar API key
| cv_api_key | | yes | Your ComicVine API key
| host | localhost | no | The host Mylar is running on.
| port | 8090 | no | The port Mylar is running on.
| urlbase | / | no | The base URL Mylar is running under.
| days | 60 | no | How many days to look back for the history sensor.
| ssl | false | no | Whether or not to use SSL for Mylar.
} monitored_conditions| history | no | A list of any of the following: history, upcoming, detailed_history, detailed_upcoming.  The detailed versions require the Upcoming Media Card component.
</br>

**Do not just copy examples, please use config options above to build your own!**
### Sample for configuration.yaml:

```
sensor:
- platform: mylar
  api_key: YOUR_API_KEY
  cv_api_key: YOUR_COMICVINE_API_KEY
  host: 192.168.1.4
  port: 8090
  days: 30
  ssl: true
  monitored_conditions:
    - detailed_upcoming
    - detailed_history
```

### Sample for ui-lovelace.yaml:

    - type: custom:upcoming-media-card
      entity: sensor.mylar_detailed_upcoming
      title: Upcoming Comics
      
      
### Card Content Defaults:

| key | default | example |
| --- | --- | --- |
| title | $title | "Captain Hickenbottom #454" |
| line1 | $episode | "Rise of the Secret Skull" |
| line2 | $release | "Wednesday, August 07, 2019" for detailed_upcoming and "4d9h ago" for detailed_history |
| line3 | $empty | blank spacer line |
| line4 | $genres | For detailed_history, contains the status, eg "Snatched" or "Post-Processed"
| icon | mdi:arrow-down-bold | https://materialdesignicons.com/icon/arrow-down-bold