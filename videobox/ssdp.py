import asyncio
import platform
import random
import socket
import struct
import time

from enum import Enum
from threading import Thread

from videobox import __version__

class Header(str, Enum):
    NT = 'nt'               # Notification Type
    NTS = 'nts'             # Notification Sub Type
    ST = 'st'               # Search Target
    USN = 'usn'             # Unique Service Name
    MX = 'mx'               # Maximum wait time
    EXT = 'ext'             # Extension acknowledge flag
    SERVER = 'server'
    CACHE_CONTROL = 'cache-control'
    LOCATION = 'location'  # Device description xml url

class Message(str, Enum):
    ALIVE = 'ssdp:alive'
    BYE = 'ssdp:byebye'
    ALL = 'ssdp:all'

class SSDPServer(asyncio.DatagramProtocol):
    """
    Simple Service Discovery Protocol
    http://www.upnp.org/specs/arch/UPnP-arch-DeviceArchitecture-v1.0-20080424.pdf
    """
    ADDRESS = '239.255.255.250'
    PORT = 1900
    # Concatenation of OS name, OS version, UPnP/1.0, product name, and product version
    SERVER_ID = f'{platform.system()},{platform.release()},UPnP/1.0,Videobox,{__version__}'

    def __init__(self, server):
        self._server = server
        print("** SSDPServer.__init__ **")

        async def _connect():
            info = socket.getaddrinfo(SSDPServer.ADDRESS, None)[0]
            sock = socket.socket(info[0], socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            group_bin = socket.inet_pton(info[0], info[4][0])
            sock.bind(('', SSDPServer.PORT))
            if info[0] == socket.AF_INET:  # IPv4
                group = group_bin + struct.pack('=I', socket.INADDR_ANY)
                sock.setsockopt(socket.IPPROTO_IP,
                                socket.IP_ADD_MEMBERSHIP, group)
            else:
                group = group_bin + struct.pack('@I', 0)
                sock.setsockopt(socket.IPPROTO_IPV6,
                                socket.IPV6_JOIN_GROUP, group)
            await asyncio.get_event_loop().create_datagram_endpoint(lambda: self, sock=sock)

        def _run(loop):
            asyncio.set_event_loop(loop)
            print("** Run loop **")
            loop.run_forever()
            loop.close()

        self.io_loop = asyncio.new_event_loop()
        asyncio.run_coroutine_threadsafe(_connect(), loop=self.io_loop)
        Thread(target=_run, args=(self.io_loop,)).start()

        self._devices_local = {}
        self._transport = None

    def connection_made(self, transport):
        print("** connection_made **", transport)
        self._transport = transport
        self._server.register_devices(self)

    def datagram_received(self, data: bytes, host_port: tuple):
        header = data.decode().split('\r\n\r\n')[0]
        lines = header.split('\r\n')
        method, target, _ = lines[0].split()
        if target != '*':
            return
        if method == 'M-SEARCH':
            headers = {x.lower(): y for x, y in (line.replace(': ', ':', 1).split(
                ':', 1) for line in lines[1:] if len(line) > 0)}
            self._m_search_received(headers, host_port)

    def register_local(self, unique_device_name, search_target, location=''):
        usn = f'{unique_device_name}::{search_target}'

        # Cache-control: The integer following max-age= specifies the number of seconds the advertisement is valid,
        # which indicates that the device need to resend this notification before expiration.
        # TODO so need to resend?!
        device = {Header.USN: usn, SSDPServer.Header.ST: search_target,
                  Header.EXT: '',  # Required by spec...confirms message was understood
                  Header.CACHE_CONTROL: 'max-age=1800',  # 1800 = 30 minutes
                  Header.SERVER: SSDPServer.SERVER_ID}
        if location:
            device[Header.LOCATION] = location

        self._devices_local[usn] = device
        self._send_alive(usn)

    def _send(self, message: str, destination: tuple):
        try:
            self._transport.sendto(message.encode(), destination)
        except socket.error as e:
            print('_send', e)

    def _send_discovery_response(self, response, destination):
        self._send(response, destination)

    @staticmethod
    def _make_message(parts, data):
        parts.extend([f'{k.value}: {v}' for k, v in data.items()])
        return '\r\n'.join(parts) + '\r\n\r\n'

    @staticmethod
    def _make_discovery_response(device):
        date = time.strftime('%a, %0d %b %Y %H:%M:%S GMT', time.gmtime())
        parts = ['HTTP/1.1 200 OK', f'date: {date}']
        return SSDPServer._make_message(parts, device)

    def _m_search_received(self, headers, host_port):
        max_delay = int(headers[Header.MX])
        search_target = headers[Header.ST]
        # The message type (MAN) for an M-Search is always "ssdp:discover"
        #  See https://williamboles.com/discovering-whats-out-there-with-ssdp/
        for device in self._devices_local.values():
            if device[Header.ST] != search_target and search_target != Message.ALL:
                continue
            response = self._make_discovery_response(device)
            # Use random delay to prevent flooding and cap at 5 seconds (see spec)
            delay = random.randint(0, min(max_delay, 5))
            asyncio.get_event_loop().call_later(
                delay, self._send_discovery_response, response, host_port)

    def _make_notify_message(self, usn, sub_type: str):
        print("** _make_notify_message **", usn, sub_type)
        device = self._devices_local[usn]
        data = device.copy()
        data[Header.NT] = data.pop(Header.ST)  # Rename ST to NT

        parts = ['NOTIFY * HTTP/1.1', 
                 f'HOST: {SSDPServer.ADDRESS}:{SSDPServer.PORT}', 
                 f'{Header.NTS.value}: {sub_type}'
                 ]
        return self._make_message(parts, data)

    def _send_alive(self, usn):
        data = self._make_notify_message(usn, Message.ALIVE.value)
        self._send(data, (SSDPServer.ADDRESS, SSDPServer.PORT))

    def _send_bye(self, usn):
        data = self._make_notify_message(usn, Message.BYE.value)
        self._send(data, (SSDPServer.ADDRESS, SSDPServer.PORT))

    def shutdown(self):
        if self._transport:
            for usn in self._devices_local:
                self._send_bye(usn)
        self.io_loop.stop()
