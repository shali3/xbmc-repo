import xbmc
import xbmcaddon
import xbmcgui
import threading
import time
import json
import urllib2
import re
import os
import datetime
import sys

__addon__ = xbmcaddon.Addon()
__cwd__ = __addon__.getAddonInfo('path')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__icon__ = __addon__.getAddonInfo('icon')
__ID__ = __addon__.getAddonInfo('id')
__language__ = __addon__.getLocalizedString

# LIB_PATH = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) )
# sys.path.append (LIB_PATH)

sound_file_path = xbmc.translatePath(os.path.join(__cwd__, 'resources', 'alert.wav'))
cities_file_path = xbmc.translatePath(os.path.join(__cwd__, 'resources', 'cities.json'))
json_data = open(cities_file_path)
area = json.load(json_data)
json_data.close()


def log(msg):
    try:
        xbmc.log(u"### [%s] - %s" % (__scriptname__, msg,), level=xbmc.LOGDEBUG)
    except:
        pass


def play_wav(full_path):
    try:
        platform = sys.platform
        if platform == "darwin":
            import subprocess

            subprocess.call(["afplay", full_path])
        elif platform == "win32":
            import winsound

            winsound.PlaySound(full_path, winsound.SND_FILENAME)
        elif platform == "linux" or platform == "linux2":
            from wave import open as waveOpen
            from ossaudiodev import open as ossOpen

            s = waveOpen('tada.wav', 'rb')
            (nc, sw, fr, nf, comptype, compname) = s.getparams()
            dsp = ossOpen('/dev/dsp', 'w')
            try:
                from ossaudiodev import AFMT_S16_NE
            except ImportError:
                if byteorder == "little":
                    AFMT_S16_NE = ossaudiodev.AFMT_S16_LE
                else:
                    AFMT_S16_NE = ossaudiodev.AFMT_S16_BE
            dsp.setparameters(AFMT_S16_NE, nc, fr)
            data = s.readframes(nf)
            s.close()
            dsp.write(data)
            dsp.close()
    except:
        log('Failed to play file %s' % full_path);
        if getSettingAsBool('play_alert_fallback'):
            xbmc.Player().play(full_path)


log("[%s] - Version: %s Started" % (__scriptname__, __version__))

# helper function to get string type from settings
def getSetting(setting):
    return __addon__.getSetting(setting).strip()


# helper function to get bool type from settings
def getSettingAsBool(setting):
    return getSetting(setting).lower() == "true"


last_id = 0


def fetch_data(url, utf16=True):
    try:
        response = urllib2.urlopen(url)
        if response.code == 200:
            text = response.read()
            if utf16:
                text = unicode(text, "utf-16")
            obj = json.loads(text)
            return obj
        else:
            log('failed getting data from %s CODE %d' % (url, response.code))
    except:
        log('failed getting data from %s' % url)


def notify_alert(cities, in_user_region=False):
    all_cities = [item for sublist in cities.values() for item in sublist]
    time = str(datetime.datetime.now().time())
    time = time[:time.find('.')]

    play_alert = in_user_region and getSettingAsBool('play_alert')

    timeout = 20000
    if in_user_region:
        timeout = 90000
    xbmcgui.Dialog().notification("Red Alert %s" % time,
                                  "%s (%s)" % (','.join(all_cities), ','.join(cities.keys()))
                                  , __icon__, timeout, not play_alert)
    player = xbmc.Player()
    if player.isPlaying():
        live_tv = player.getPlayingFile().find("pvr://") > -1
        if (live_tv and getSettingAsBool('pause_live_tv')) or (not live_tv and getSettingAsBool('pause_other')):
            player.pause()

    if play_alert:
        play_wav(sound_file_path)


def process_json(obj):
    global last_id
    if obj:
        new_id = obj.get("id")
        if new_id != last_id:
            alert_regions = re.findall("\d+", getSetting('alert_code'))
            in_user_region = False
            notifyAll = getSettingAsBool('notify_all')
            last_id = new_id
            cities = {}  # code to cities names
            data = obj.get("data")

            for item in data:
                for city in item.split(','):
                    code = re.sub("[^\d]+", "", city).strip()

                    if len(alert_regions) == 0 or notifyAll or code in alert_regions:
                        if code in alert_regions:
                            in_user_region = True
                        cities_names = cities.get(code, [])
                        cities_names += area.get(city, [])
                        cities[code] = cities_names

            if len(cities) > 0:
                notify_alert(cities, in_user_region)


def check_for_alerts():
    global last_id
    # obj = fetch_data('http://dl.dropboxusercontent.com/u/8058232/testing/alerts.json', False);  # Testing url...
    obj = fetch_data('http://www.oref.org.il/WarningMessages/alerts.json', True);
    process_json(obj)


if len(getSetting('alert_code').strip()) == 0:
    response = xbmcgui.Dialog().ok("Red Alert Israel",
                                   'You need to specify region codes you want to be alerted on. '
                                   'You can find them at oref.gov.il.\n'
                                   'You can specify more than one by separating with spaces.\n'
                                   'For example: Tel-Aviv is 157 and Givataim is 160.')
    if response:
        xbmcaddon.Addon().openSettings()

counter = 0;
while not xbmc.abortRequested:
    if counter == 0:
        check_for_alerts()
    counter = (counter + 1) % 30
    xbmc.sleep(100)  # low sleep to keep the quit process quick