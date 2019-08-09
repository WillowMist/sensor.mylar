""""Support for Mylar."""
import logging
import time
import calendar
import datetime
import json
import tempfile
import os

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_MONITORED_CONDITIONS,
    CONF_SSL,
)
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

CONF_DAYS = "days"
CONF_INCLUDED = "include_paths"
CONF_UNIT = "unit"
CONF_URLBASE = "urlbase"
CONF_CV_API_KEY = "cv_api_key"

DEFAULT_DAYS = "5"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8090
DEFAULT_URLBASE = ""
DEFAULT_UNIT = "MB"

SENSOR_TYPES = {
    "history": ["History", "Items", "mdi:history"],
    "detailed_history": ["Detailed History", "Items", "mdi:history"],
    "upcoming": ["Upcoming", "Issues", "mdi:book-open-variant"],
    "detailed_upcoming": ["Detailed Upcoming", "Issues", "mdi:book-open-variant"],
}


ENDPOINTS = {
    "detailed_history": "http{0}://{1}:{2}/{3}api?apikey={4}&cmd=getHistory",
    "history": "http{0}://{1}:{2}/{3}api?apikey={4}&cmd=getHistory",
    "detailed_upcoming": "http{0}://{1}:{2}/{3}api?apikey={4}&cmd=getUpcoming",
    "upcoming": "http{0}://{1}:{2}/{3}api?apikey={4}&cmd=getUpcoming",
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_CV_API_KEY): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_INCLUDED, default=[]): cv.ensure_list,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["history"]): vol.All(
            cv.ensure_list, [vol.In(list(SENSOR_TYPES))]
        ),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_SSL, default=False): cv.boolean,
        vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): cv.string,
        vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Mylar platform."""
    conditions = config.get(CONF_MONITORED_CONDITIONS)
    add_entities([MylarSensor(hass, config, sensor) for sensor in conditions], True)


class MylarSensor(Entity):
    """Implementation of the Mylar sensor."""

    def __init__(self, hass, conf, sensor_type):
        """Create Mylar entity."""
        from pytz import timezone

        self.conf = conf
        self.host = conf.get(CONF_HOST)
        self.port = conf.get(CONF_PORT)
        self.urlbase = conf.get(CONF_URLBASE)
        if self.urlbase:
            self.urlbase = "{}/".format(self.urlbase.strip("/"))
        self.apikey = conf.get(CONF_API_KEY)
        self.cvapikey = conf.get(CONF_CV_API_KEY)
        self.included = conf.get(CONF_INCLUDED)
        self.days = int(conf.get(CONF_DAYS))
        self.ssl = "s" if conf.get(CONF_SSL) else ""
        self._state = None
        self.data = []
        self._tz = timezone(str(hass.config.time_zone))
        self.type = sensor_type
        self._name = SENSOR_TYPES[self.type][0]
        self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]
        self._available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format("Mylar", self._name)

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @property
    def available(self):
        """Return sensor availability."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}
        if self.type == "history":
            for entry in self.data:
                if entry['Status'] == 'Snatched':
                    status = "SN"
                elif entry['Status'] == 'Post-Processed':
                    status = "PP"
                else:
                    status = "D"
                d = datetime.datetime.strptime(entry["DateAdded"], "%Y-%m-%d %H:%M:%S")
                comic = '%s #%s' % (entry["ComicName"][:30], entry["Issue_Number"])
                if comic in attributes.keys():
                    attributes[comic] += '\n'
                else:
                    attributes[comic] = ''
                attributes[comic] += " {}|{}".format(
                    timesince(d), status
                )
        elif self.type == "detailed_history":
            card_json = []
            default = {}
            default['title_default'] = '$title'
            default['line1_default'] = '$episode'
            default['line2_default'] = '$release'
            default['line3_default'] = '$empty'
            default['line4_default'] = '$genres'
            default['icon'] = 'mdi:arrow-down-bold'
            card_json.append(default)
            for entry in self.data:
                card_item = {}
                if 'image' in entry['cvdata']:
                    card_item['poster'] = entry['cvdata']['image']['thumb_url']
                else:
                    card_item['poster'] = 'https://via.placeholder.com/121x160?text=Image+not+found'
                d = datetime.datetime.strptime(entry["DateAdded"], "%Y-%m-%d %H:%M:%S")
                card_item['airdate'] = d.isoformat()
                card_item['title'] = '%s #%s' % (entry['ComicName'], entry['Issue_Number'])
                card_item['genres'] = entry['Status']
                card_item['episode'] = entry['cvdata']['name'] if 'name' in entry['cvdata'] else ''
                card_item['release'] = timesince(d)
                card_json.append(card_item)
            attributes['data'] = json.dumps(card_json)
        elif self.type == "upcoming":
            for entry in self.data:
                attributes['%s #%s' % (entry['ComicName'], entry['IssueNumber'])] = entry['IssueDate']
        elif self.type == "detailed_upcoming":
            card_json = []
            default = {}
            default['title_default'] = '$title'
            default['line1_default'] = '$episode'
            default['line2_default'] = '$release'
            default['line3_default'] = '$empty'
            default['line4_default'] = ''
            default['icon'] = 'mdi:arrow-down-bold'
            card_json.append(default)
            for entry in self.data:
                card_item = {}
                if 'image' in entry['cvdata']:
                    card_item['poster'] = entry['cvdata']['image']['thumb_url']
                else:
                    card_item['poster'] = 'https://via.placeholder.com/121x160?text=Image+not+found'
                card_item['episode'] = entry['cvdata']['name'] if 'name' in entry['cvdata'] else ''
                d = datetime.datetime.strptime(entry["IssueDate"], "%Y-%m-%d")
                card_item['airdate'] = d.isoformat()
                card_item['title'] = '%s #%s' % (entry['ComicName'], entry['IssueNumber'])
                card_item['release'] = d.strftime('%A, %B %d, %Y')
                card_json.append(card_item)
            attributes['data'] = json.dumps(card_json)
        return attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    def update(self):
        """Update the data for the sensor."""
        try:
            req = ENDPOINTS[self.type].format(self.ssl, self.host, self.port, self.urlbase, self.apikey)
            res = requests.get(
                req,
                timeout=30,
            )
        except OSError:
            _LOGGER.warning("Host %s is not available", self.host)
            self._available = False
            self._state = None
            return
        tempfolder = tempfile.gettempdir()
        cachefilename = 'mylar.cache'
        cachefile = os.path.join(tempfolder, cachefilename)
        if not os.path.exists(cachefile):
            cache = {}
        else:
            with open(cachefile) as json_file:
                cache = json.load(json_file)

        if res.status_code == 200:
            if self.type in ["history", "detailed_history"]:
                tempdata = res.json()['data']
                self.data = []
                now = datetime.datetime.now()
                for entry in tempdata:
                    try:
                        d = datetime.datetime.strptime(entry["DateAdded"], "%Y-%m-%d %H:%M:%S")
                        agedelta = now - d
                        if agedelta.days <= self.days:
                            if self.type == "detailed_history":
                                issueid = entry['IssueID'] if 'IssueID' in entry.keys() else None
                                if issueid in cache.keys():
                                    cvdata = cache[issueid]
                                else:
                                    cvdata = get_cvdata(self.cvapikey, issueid=issueid)
                                    cache[issueid] = cvdata
                                entry['cvdata'] = cvdata
                            self.data.append(entry)
                    except Exception as e:
                        _LOGGER.error("Error: %s\nEntry: %s" % (e, entry))
                self._state = len(self.data)
            elif self.type in ["upcoming"]:
                self.data = res.json()
                self._state = len(self.data)
            elif self.type == "detailed_upcoming":
                tempdata = res.json()
                self.data = []
                for entry in tempdata:
                    issueid = entry['IssueID'] if 'IssueID' in entry.keys() else None
                    if issueid:
                        if issueid in cache.keys():
                            cvdata = cache[issueid]
                        else:
                            cvdata = get_cvdata(self.cvapikey, issueid=issueid)
                            cache[issueid] = cvdata
                    else:
                        comicid = entry['ComicID']
                        issuenumber = entry['IssueNumber']
                        cvid = '%s|%s' % (comicid, issuenumber)
                        if cvid in cache.keys():
                            cvdata = cache[cvid]
                        else:
                            cvdata = get_cvdata(self.cvapikey, volumeid=comicid, issuenumber=issuenumber)
                            cache[cvid] = cvdata
                    entry['cvdata'] = cvdata
                    self.data.append(entry)
                    self._state = len(self.data)
            with open(cachefile, 'w') as json_file:
                json.dump(cache, json_file)

            self._available = True


def get_date(zone, offset=0):
    """Get date based on timezone and offset of days."""
    day = 60 * 60 * 24
    return datetime.datetime.date(datetime.datetime.fromtimestamp(time.time() + day * offset, tz=zone))


def get_cvdata(apikey, issueid=None, volumeid=None, issuenumber=None):
    cvbaseurl = 'https://comicvine.gamespot.com/api/issues'
    if issueid:
        cvurl = '%s?api_key=%s&filter=id:%s&format=json' % (cvbaseurl, apikey, issueid)
    elif volumeid and issuenumber:
        cvurl = '%s?api_key=%s&filter=volume:%s,issue_number:%s&format=json' % (cvbaseurl, apikey, volumeid, issuenumber)
    try:
        user_agent = {'User-agent': 'HomeAssistant'}
        cvres = requests.get(cvurl, headers = user_agent, timeout=20)
    except OSError:
        _LOGGER.warning("CV Host is not available")
        return

    if cvres.status_code == 200:
        cvdata = cvres.json()
        _LOGGER.info("Data: %s" % cvdata)
        if 'results' in cvdata.keys() and len(cvdata['results']):
            data = cvdata['results'][0]
            data['cvurl'] = cvurl
            return data

    else:
        _LOGGER.info("Failed: %s" % cvres.status_code)
    return {'cvurl': cvurl, 'cvres': cvres.status_code}


TIME_STRINGS = {
    'year': '%dy',
    'month': '%dmo',
    'week': '%dw',
    'day': '%dd',
    'hour': '%dh',
    'minute': '%dmin',
}

TIMESINCE_CHUNKS = (
    (60 * 60 * 24 * 365, 'year'),
    (60 * 60 * 24 * 30, 'month'),
    (60 * 60 * 24 * 7, 'week'),
    (60 * 60 * 24, 'day'),
    (60 * 60, 'hour'),
    (60, 'minute'),
)


def timesince(d, now=None, time_strings=None):

    if time_strings is None:
        time_strings = TIME_STRINGS

    # Convert datetime.date to datetime.datetime for comparison.
    if not isinstance(d, datetime.datetime):
        d = datetime.datetime(d.year, d.month, d.day)
    if now and not isinstance(now, datetime.datetime):
        now = datetime.datetime(now.year, now.month, now.day)

    now = now or datetime.datetime.now()

    delta = now - d

    # Deal with leapyears by subtracing the number of leapdays
    leapdays = calendar.leapdays(d.year, now.year)
    if leapdays != 0:
        if calendar.isleap(d.year):
            leapdays -= 1
        elif calendar.isleap(now.year):
            leapdays += 1
    delta -= datetime.timedelta(leapdays)

    # ignore microseconds
    since = delta.days * 24 * 60 * 60 + delta.seconds
    if since <= 0:
        # d is in the future compared to now, stop processing.
        return '0 minutes'
    for i, (seconds, name) in enumerate(TIMESINCE_CHUNKS):
        count = since // seconds
        if count != 0:
            break
    result = time_strings[name] % count
    if i + 1 < len(TIMESINCE_CHUNKS):
        # Now get the second item
        seconds2, name2 = TIMESINCE_CHUNKS[i + 1]
        count2 = (since - (seconds * count)) // seconds2
        if count2 != 0:
            result += time_strings[name2] % count2
    return result
