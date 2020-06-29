
import asyncio
import hashlib
import json
import logging
import os
import secrets
import socket
import sys
from threading import Thread

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
        self.render(os.path.join(self.path, 'index.html'))


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


# Create a socket
def sendPacket(MESSAGE, IP, Port):
    try:
        sock = socket.socket(socket.AF_INET,
                             socket.SOCK_DGRAM)
        sock.settimeout(5)
        # Send message to UDP port
        print(f'sending message to {IP}:{Port}')
        sent = sock.sendto(MESSAGE, (IP, Port))

        # Receive response
        print('waiting to receive')
        data, server = sock.recvfrom(4096)
        print('received "%s"' % data)
        return True
    except:
        return False


def start_WebServer():
    ws = WebServer()

    def start_server():
        if sys.version_info.minor > 7:
            asyncio.set_event_loop_policy(
                asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.set_event_loop(asyncio.new_event_loop())
        ws.run()

    t = Thread(target=start_server, args=())
    t.start()


if __name__ == "__main__":
    start_WebServer()
