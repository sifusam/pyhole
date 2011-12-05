#   Copyright 2011 Jesse Gonzalez
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""Pyhole Zenoss Plugin"""

from pyhole import plugin
from pyhole import utils
import json
import urllib
import urllib2
import time

class Zenoss(plugin.Plugin):
    """Provide access to the Zenoss Events """

    def __init__(self, irc):
        self.irc = irc
        self.name = self.__class__.__name__
        self.disabled = False
        self._connected = False

        self.severity = ['clear', 'debug', 'info', 'warning', 'error', 'critical']
        self.severitycolor = [15, 13, 11, 8, 5, 40]

        try:
            self.zenoss = utils.get_config("Zenoss")
            self.zenoss_server = self.zenoss.get("server")
            self.zenoss_user = self.zenoss.get("user")
            self.zenoss_password = self.zenoss.get("password")
            self.zenoss_port = self.zenoss.get("port")
            self.zenoss_url = "http://%s:%s" % (self.zenoss_server, self.zenoss_port)
        except Exception:
            self.irc.reply("You need to add a configuration section for [Zenoss].")
            self.disabled = True

    def _connect_zenoss(self):
            """Initialize a connection to the Zenoss API"""

            self.urlOpener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
            self.reqCount = 1

            loginParams = urllib.urlencode(dict(
                __ac_name = self.zenoss_user,
                __ac_password = self.zenoss_password,
                submitted = 'true',
                came_from = self.zenoss_url + '/zport/dmd'))
            self.urlOpener.open(self.zenoss_url + '/zport/acl_users/cookieAuthHelper/login',
                    loginParams)
            self._connected = True

    def _router_request(self, router, method, data=[]):
        # Contruct a standard URL request for API calls
        req = urllib2.Request(self.zenoss_url + '/zport/dmd/' +
                              router + '_router')

        # NOTE: Content-type MUST be set to 'application/json' for these requests
        req.add_header('Content-type', 'application/json; charset=utf-8')

        # Convert the request parameters into JSON
        reqData = json.dumps([dict(
                    action='EventsRouter',
                    method=method,
                    data=data,
                    type='rpc',
                    tid=self.reqCount)])

        # Increment the request count ('tid'). More important if sending multiple
        # calls in a single request
        self.reqCount += 1

        # Submit the request and convert the returned JSON to objects
        return json.loads(self.urlOpener.open(req, reqData).read())

    def _get_events(self, device=None, component=None, eventClass=None):
        data = dict(start=0, limit=1000, dir='DESC', sort='severity')
        data['params'] = dict(severity=[5,4,3,2], eventState=[0,1])

        if device: data['params']['device'] = device
        if component: data['params']['component'] = component
        if eventClass: data['params']['eventClass'] = eventClass

        return self._router_request('evconsole', 'query', [data])['result']


    @plugin.hook_add_command("zenbot")
    @utils.spawn
    def zenbot(self, params=None, **kwargs):
        """Pull the latest Zenoss Events (ex: .zenbot"""

        if self._connected == False:
            api = self._connect_zenoss()

        events = self._get_events()['events']

        eventCount = events.__len__()
        severe = 0 
        for event in events:
            if int(event['severity']) == 5:
                severe += 1
        self.irc.reply("There are currently " + str(eventCount) + " events, " + str(severe) + " are critical.")

        time.sleep(.25)

        #if details != False:
        if True:
            if eventCount <= 25:
                target = self.irc.target
            else:
                self.irc.reply("There are more than 25 events. Sending via privmsg.")
                target = self.irc.split("!")[0]
            for event in events:
                severity = int(event['severity'])
                eventState = event['eventState']
                eventId = event['id']
                device = event['device']['text']
                component = event['component']['text']
                summary = event['summary']
                severity_color = self.severitycolor[severity]

                self.irc.privmsg(target, "\003%02d%s - ID: %s - %s - %s -- %s" % (severity_color, eventState, eventId, device,
                    component, summary))
                time.sleep(.25)
                print(dir(self.irc.ircobj))

    @plugin.hook_add_command("zb")
    def alias_cb(self, params=None, **kwargs):
        """Alias of zenbot"""
        self.zenbot(params, **kwargs)

