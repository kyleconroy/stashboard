# Copyright (c) 2010 Twilio Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import datetime
import urlparse
from datetime import timedelta
from datetime import date
from google.appengine.ext import db
from time import mktime
from wsgiref.handlers import format_date_time

class Level(object):
    """
    A fake db.Model object, just in case we want to actually store things
    in the future
    """
    levels = {
        "NORMAL": 10,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
    }

    normal  = "NORMAL"
    warning = "WARNING"
    critial = "CRITICAL"
    error   = "ERROR"

    @staticmethod
    def all():
        llist = []
        for k in Level.levels.keys():
            llist.append((k, Level.levels[k]))

        return map(lambda x: x[0], sorted(llist, key=lambda x: x[1]))

    @staticmethod
    def get_severity(level):
        try:
            return Level.levels[level]
        except:
            return False

    @staticmethod
    def get_level(severity):
        for k in Level.levels.keys():
            if Level.levels[k] == severity:
                return k
        return False


class Service(db.Model):
    """A service to track

        Properties:
        name        -- string: The name of this service
        description -- string: The function of the service
        slug        -- stirng: URL friendly version of the name

    """
    @staticmethod
    def get_by_slug(service_slug):
        return Service.all().filter('slug = ', service_slug).get()

    slug = db.StringProperty(required=True)
    name = db.StringProperty(required=True)
    description = db.StringProperty(required=True)

    def current_event(self):
        event = self.events.order('-start').get()
        return event

    def url(self):
        return "/services/%s" % self.slug

    #Specialty function for front page
    def history(self, days, lowest):
        # Lowest severity of a status
        severity = lowest.severity

        yesterday = date.today() - timedelta(days=1)
        ago = yesterday - timedelta(days=days)

        events = self.events.filter('start >', ago) \
            .filter('start <', yesterday).fetch(100)

        stats = {}

        for i in range(5):
            stats[yesterday.day] = {
                "image": lowest.image,
                "name": lowest.name,
                "day": yesterday,
            }
            yesterday = yesterday - timedelta(days=1)

        for event in events:
            if event.status.severity > severity:
                stats[event.start.day]["image"] = "icons/fugue/information.png"
                stats[event.start.day]["information"] = True
                stats[event.start.day]["name"] = "information"

        keys = stats.keys()
        keys.sort()
        keys.reverse()

        return [ stats[k] for k in keys]


    def compare(self, other_status):
        return 0

    def sid(self):
        return str(self.key())

    def resource_url(self):
        return "/services/" + self.slug

    def rest(self, base_url):
        """ Return a Python object representing this model"""

        m = {}
        m["name"] = str(self.name)
        m["id"] = str(self.slug)
        m["description"] = str(self.description)
        m["url"] = base_url + self.resource_url()

        event = self.current_event()
        if event:
            m["current-event"] = event.rest(base_url)
        else:
            m["current-event"] = None

        return m

class Status(db.Model):
    """A possible system status

        Properties:
        name        -- string: The friendly name of this status
        slug        -- stirng: The identifier for the status
        description -- string: The state this status represents
        image       -- string: Image in /images/status
        severity    -- int: The serverity of this status

    """
    @classmethod
    def get_by_slug(cls, status_slug):
        return cls.all().filter('slug = ', status_slug).get()

    @classmethod
    def default(cls):
        """
        Return the first status with a NORMAL level.
        """
        normal = Level.get_severity(Level.normal)
        return cls.all().filter('severity == ', normal).get()

    @classmethod
    def install_defaults(cls):
        """
        Install the default statuses. xI am not sure where these should live just yet
        """
        # This should be Level.normal.severity and Level.normal.text
        normal = Level.get_severity(Level.normal)
        warning = Level.get_severity(Level.warning)
        error = Level.get_severity(Level.error)


        if not cls.get_by_slug("down"):
            d = cls(name="Down", slug="down", severity=error,
                    image="icons/fugue/cross-circle.png",
                    description="The service is currently down")
            d.put()

        if not cls.get_by_slug("up"):
            u = cls(name="Up", slug="up", severity=normal,
                    image="icons/fugue/tick-circle.png",
                    description="The service is up")
            u.put()

        if not cls.get_by_slug("warning"):
            w = cls(name="Warning", slug="warning", severity=warning,
                    image="icons/fugue/exclamation.png",
                    description="The service is experiencing intermittent problems")
            w.put()

    name = db.StringProperty(required=True)
    slug = db.StringProperty(required=True)
    description = db.StringProperty(required=True)
    image = db.StringProperty(required=True)
    severity = db.IntegerProperty(required=True)

    def image_url(self):
        return "/images/status/" + unicode(self.image) + ".png"

    def resource_url(self):
        return "/statuses/" + str(self.slug)

    def rest(self, base_url):
        """ Return a Python object representing this model"""

        m = {}
        m["name"] = str(self.name)
        m["id"] = str(self.slug)
        m["description"] = str(self.description)
        m["level"] = Level.get_level(int(self.severity))
        m["url"] = base_url + self.resource_url()
        # This link shouldn't be hardcoded

        o = urlparse.urlparse(base_url)
        m["image"] = o.scheme + "://" +  o.netloc + self.image_url()

        return m


class Event(db.Model):

    start = db.DateTimeProperty(required=True, auto_now_add=True)

    # We want this to be required, but it would break all current installs
    # Instead, we handle it in the rest method
    informational = db.BooleanProperty(default=False)
    status = db.ReferenceProperty(Status, required=True)
    message = db.TextProperty(required=True)
    service = db.ReferenceProperty(Service, required=True,
        collection_name="events")

    def duration(self):
        # calculate the difference between start and end
        # should evantually be stored
        pass

    def sid(self):
        return str(self.key())

    def resource_url(self):
        return self.service.resource_url() + "/events/" + self.sid()

    def rest(self, base_url):
        """ Return a Python object representing this model"""

        m = {}
        m["sid"] = self.sid()

        stamp = mktime(self.start.timetuple())
        m["timestamp"] = format_date_time(stamp)
        m["status"] = self.status.rest(base_url)
        m["message"] = str(self.message)
        m["url"] = base_url + self.resource_url()

        if self.informational:
            m["informational"] = self.informational
        else:
            m["informational"] = False

        return m

class Profile(db.Model):
    owner = db.UserProperty(required=True)
    token = db.StringProperty(required=True)
    secret = db.StringProperty(required=True)

class AuthRequest(db.Model):
    owner = db.UserProperty(required=True)
    request_secret = db.StringProperty()

class Setting(db.Model):
    name = db.StringProperty(required=True)

