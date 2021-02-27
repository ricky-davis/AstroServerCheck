
import json
import os
import socket
#from pprint import pprint

import arrow
import requests
import tornado.web
from cachetools import TTLCache
from packaging import version

# pylint: disable=abstract-method,attribute-defined-outside-init,no-member


base_headers = {
    "Content-Type": "application/json; charset=utf-8",
    "X-PlayFabSDK": "UE4MKPL-1.19.190610",
    "User-Agent": "game=Astro, engine=UE4, version=4.18.2-0+++UE4+Release-4.18, platform=Windows, osver=6.2.9200.1.256.64bit",
}


def generate_XAUTH(serverGUID):
    url = "https://5EA1.playfabapi.com/Client/LoginWithCustomID?sdk=UE4MKPL-1.19.190610"
    requestObj = {"CreateAccount": True,
                  "CustomId": serverGUID, "TitleId": "5EA1"}
    x = (requests.post(url, headers=base_headers, json=requestObj)).json()
    return x["data"]["SessionTicket"]


def get_all_servers(headers):
    url = "https://5EA1.playfabapi.com/Client/GetCurrentGames?sdk=UE4MKPL-1.19.190610"
    x = (requests.post(url, headers=headers, json={})).json()
    return x


class WebServer(tornado.web.Application):
    def __init__(self):
        self.serverCache = TTLCache(maxsize=500, ttl=10)
        self.lastPFData = None
        self.maxServerVersion = "0.0"
        self.fullStatsData = {}
        self.allServerData = {}
        settings = {
            'debug': True,
            "static_path": "public",
        }
        handlers = [(r'/', MainHandler, {"path": settings['static_path']}),
                    (r"/api", APIRequestHandler),
                    (r"/stats", StatsRequestHandler)
                    ]
        super().__init__(handlers, **settings)

    def run(self):
        port = 5555
        self.listen(port)
        url = f"http://localhost:{port}"
        print(f"Running a web server at {url}")
        tornado.ioloop.IOLoop.instance().start()


class MainHandler(tornado.web.RequestHandler):
    # pylint: disable=arguments-differ

    def initialize(self, path):
        self.path = path

    def get(self):
        clientIP = self.request.headers.get("X-Real-IP") or \
            self.request.headers.get("X-Forwarded-For") or \
            self.request.remote_ip
        clientPort = '8777'
        args = self.request.arguments

        if 'url' in args:
            url = (args['url'][0]).split(b":")
            if len(url) > 0:
                clientIP = url[0]
            if len(url) > 1 and url[1] != b'':
                clientPort = url[1]
        else:
            if 'ip' in args:
                clientIP = (args['ip'][0])
            if 'port' in args:
                clientPort = (args['port'][0])

        # pprint(list(self.request.headers.get_all()))
        print(f"Webpage opened at: {self.request.headers.get('X-Real-IP')}")
        self.render(os.path.join(self.path, 'index.html'),
                    clientIP=clientIP, clientPort=clientPort)


class StatsRequestHandler(tornado.web.RequestHandler):
    # pylint: disable=arguments-differ
    def pull_latest_data(self):
        if self.application.lastPFData is None or (arrow.utcnow() - self.application.lastPFData).seconds >= 10:
            headers = base_headers
            headers["X-Authorization"] = generate_XAUTH("7")
            apfData = get_all_servers(headers)
            if len(apfData['data']['Games']) > 0:
                apfData = apfData['data']['Games']
                self.application.allServerData = apfData

                allVers = [x['Tags']['gameBuild'] for x in apfData]
                maxVers = "0.0"
                for v in allVers:
                    if version.parse(v) > version.parse(maxVers) and allVers.count(v) > 5:
                        maxVers = v
                self.application.maxServerVersion = maxVers

    def get_stats(self, serverList, maxVers):
        data = {
            "serverCount": 0,
            "playerCount": 0,
            "upToDate": 0,
            "hasPassword": 0,
            "emptyServers": 0,
        }
        # pprint(serverList)
        data["serverCount"] = len(serverList)
        data["playerCount"] = sum(
            [int(x['Tags']["numPlayers"]) for x in serverList])
        data["upToDate"] = sum([(version.parse(
            x['Tags']['gameBuild']) >= version.parse(maxVers)) for x in serverList])

        data["hasPassword"] = sum(
            [(x['Tags']['requiresPassword'] == 'true') for x in serverList])

        data["emptyServers"] = sum(
            [(int(x['Tags']["numPlayers"]) == 0) for x in serverList])
        return data

    def get(self):
        FullStatsData = {
            "LatestVersion": "0.0",
            "Total": {},
            "Preferred": {},
            "Individual": {},
        }
        self.pull_latest_data()
        if self.application.lastPFData is None or (arrow.utcnow() - self.application.lastPFData).seconds >= 10:
            aSD = self.application.allServerData
            maxVers = self.application.maxServerVersion
            FullStatsData["LatestVersion"] = maxVers

            preferredServers = [x for x in aSD if x['Tags']
                                ['category'] == "Preferred"]
            individualServers = [
                x for x in aSD if x['Tags']['category'] == "Individual"]

            FullStatsData["Total"] = self.get_stats(aSD, maxVers)
            FullStatsData["Preferred"] = self.get_stats(
                preferredServers, maxVers)
            FullStatsData["Individual"] = self.get_stats(
                individualServers, maxVers)
            self.application.fullStatsData = FullStatsData

        self.write(self.application.fullStatsData)


class APIRequestHandler(tornado.web.RequestHandler):
    # pylint: disable=arguments-differ
    def post(self):
        # "70.130.124.250"  # Target IP Address
        UDP_IP_PORT = self.get_argument("ip_port")
        UDP_IP = None
        UDP_PORT = None
        splitIPP = UDP_IP_PORT.split(":")
        if len(splitIPP) > 0:
            UDP_IP = splitIPP[0]
            if(len(splitIPP) > 1) and splitIPP[1] != b'':
                UDP_PORT = splitIPP[1]
            else:
                UDP_PORT = "8777"
            UDP_IP_PORT = UDP_IP+":"+UDP_PORT
            UDP_PORT = int(UDP_PORT)
            ipPortCombo = f"{UDP_IP_PORT}"
            data = {
                "Server": False,
                "Playfab": False,
                "Version": 0,
                "UpToDate": True,
                "LatestVersion": "0.0",
                "PlayerCount": "0/12",
                "Password": False,
                "Type": "Unknown",
                "Fresh": True,
            }

            if ipPortCombo not in self.application.serverCache:
                byteArray = [0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                             0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x08]
                res = sendPacket(bytes(byteArray), UDP_IP, UDP_PORT)
                data['Server'] = res

                StatsRequestHandler.pull_latest_data(self)

                aSD = self.application.allServerData
                maxVers = self.application.maxServerVersion

                pfData = [x for x in aSD if x['Tags']
                          ['gameId'] == ipPortCombo]

                if len(pfData) > 0:
                    pfData = pfData[0]
                    data['Playfab'] = True
                    data['Type'] = pfData['Tags']['category']
                    if data['Type'] == "Individual":
                        data['Type'] = "Self-Hosted"
                        if "customdata" in pfData['Tags']['serverName']:
                            cdata = json.loads(pfData['Tags']['serverName'])[
                                'customdata']
                            data['Type'] = f"{cdata['ServerType']}"
                    else:
                        data['Type'] = "Nitrado"

                    data['Version'] = pfData['Tags']['gameBuild']

                    data['UpToDate'] = version.parse(
                        data['Version']) >= version.parse(maxVers)

                    data['PlayerCount'] = f"{len(pfData['PlayerUserIds'])}/{pfData['Tags']['maxPlayers']}"
                    data['Password'] = pfData['Tags']['requiresPassword']

                data['Fresh'] = True
                self.application.serverCache[ipPortCombo] = data

            else:
                data = self.application.serverCache[ipPortCombo]
                data['Fresh'] = False

            self.write(data)
        else:
            self.write({"status": "Error"})


def check_ipv6(n):
    try:
        socket.inet_pton(socket.AF_INET6, n)
        print(f"{n} is IPV6!")
        return True
    except socket.error:
        print(f"{n} is IPV4!")
        return False

# Create a socket


def sendPacket(MESSAGE, IP, Port):
    try:
        if check_ipv6(IP):
            sock = socket.socket(socket.AF_INET6,
                                 socket.SOCK_DGRAM)
        else:
            sock = socket.socket(socket.AF_INET,
                                 socket.SOCK_DGRAM)
        sock.settimeout(5)
        # Send message to UDP port
        print(f'sending message to {IP}:{Port}')
        sock.sendto(MESSAGE, (IP, Port))

        # Receive response
        print('waiting to receive')
        sock.settimeout(5)
        data, _server = sock.recvfrom(4096)
        print('received "%s"' % data)
        return True
    except:
        print(f"Timeout for {IP}:{Port}")
        return False


def start_WebServer():
    ws = WebServer()

    ws.run()


if __name__ == "__main__":
    try:
        start_WebServer()
    except KeyboardInterrupt:
        print("WebServer was killed by CTRL+C")
