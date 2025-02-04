"""
Simple Service Discovery Protocol
http://www.upnp.org/specs/arch/UPnP-arch-DeviceArchitecture-v1.0-20080424.pdf
"""

import asyncio
import platform
import socket
# import time
from flask import current_app
# from enum import Enum
from threading import Thread, Event
import ssdp

from videobox import __version__

ssdp_worker = None

SERVER_ID = f'{platform.system()},{platform.release()},UPnP/1.0,Videobox,{__version__}'

class SSDPWorker(Thread):
    def __init__(self):
        super().__init__(name="SSDP worker")
        self.abort_event = Event()
        self.loop = asyncio.new_event_loop()
        connect = self.loop.create_datagram_endpoint(MyProtocol, family=socket.AF_INET)
        self.transport, _ = self.loop.run_until_complete(connect)

    def run(self):
        async def wait_for_abort():
            while not self.abort_event.is_set():
                await asyncio.sleep(1)
            print("Stopping the loop")
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(wait_for_abort())


    def abort(self):
        self.abort_event.set()
        self.loop.call_soon_threadsafe(self.loop.stop)
        # self.join()

        self.transport.close()
    

class MyProtocol(ssdp.aio.SimpleServiceDiscoveryProtocol):

    def __init__(self):
        self._devices_local = {}

    def connection_made(self, transport):
        # self._send_alive
        pass
    
    def response_received(self, response, addr):
        print(response, addr)

    def request_received(self, request, addr):
        print(request, addr)

    def _m_search_received(self, request, addr):
        pass

    def _send_alive(self, usn):
        notify = ssdp.SSDPRequest('NOTIFY', headers={
            'HOST': '10.0.0.42',
            'NT': 'upnp:rootdevice',
            'NTS': 'ssdp:alive',
        })        
        notify.sendto(self.transport, (ssdp.network.MULTICAST_ADDRESS_IPV4, ssdp.network.PORT))

    def _send_bye(self, usn):
        notify = ssdp.SSDPRequest('NOTIFY', headers={
            'HOST': '10.0.0.42',
            'NT': 'upnp:rootdevice',
            'NTS': 'ssdp:byebye',
        })    
        notify.sendto(self.transport, (ssdp.network.MULTICAST_ADDRESS_IPV4, ssdp.network.PORT))

