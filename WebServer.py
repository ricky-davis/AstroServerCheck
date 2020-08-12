
import json
import os
import socket

import tornado.web
from cachetools import TTLCache

# pylint: disable=abstract-method,attribute-defined-outside-init,no-member


class WebServer(tornado.web.Application):
    def __init__(self):
        self.serverCache = TTLCache(maxsize=500, ttl=10)
        settings = {
            'debug': True,
            "static_path": "public",
        }
        handlers = [(r'/', MainHandler, {"path": settings['static_path']}),
                    (r"/api", APIRequestHandler)
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
            clientIP = url[0]
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


class APIRequestHandler(tornado.web.RequestHandler):
    # pylint: disable=arguments-differ
    def post(self):
        # "70.130.124.250"  # Target IP Address
        UDP_IP = self.get_argument("ip")
        UDP_PORT = int(self.get_argument("port"))  # 8777
        ipPortCombo = f"{UDP_IP}:{UDP_PORT}"

        if ipPortCombo not in self.application.serverCache:
            byteArray = [0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04]
            res = sendPacket(bytes(byteArray), UDP_IP, UDP_PORT)
            self.application.serverCache[ipPortCombo] = res
            fresh = True
        else:
            res = self.application.serverCache[ipPortCombo]
            fresh = False
        if res:
            self.write(json.dumps({'status': 'Success', "fresh": fresh}))
        else:
            self.write(json.dumps({'status': 'Error'}))


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
