# coding: utf-8
#
# handlers for atxslave
#

import json
import uuid
from tornado.ioloop import IOLoop
from logzero import logger

from ..database import db, time_now
from .base import BaseRequestHandler, BaseWebSocketHandler


class SlaveHeartbeatWSHandler(BaseWebSocketHandler):
    """ monitor device online or offline """

    def initialize(self):
        self._owner = None
        self._id = None
        self._slaves = {}
        self._info = None

    def open(self):
        """
        id: xxxx,
        name: xxxx,
        bindAddress: "10.0.0.1:6477",
        """
        logger.info("new websocket connected: %s", self.request.remote_ip)
        pass

    async def _on_ping(self, req):
        """
        {"command": "ping"}
        """
        self.write_message("pong")

    async def _on_handshake(self, req: dict):
        """
        identify slave self

        {"command": "handshake",
         "name": "ccddqq",
         "owner": "someone@domain.com"}
        """
        assert "name" in req
        assert "priority" in req
        req.pop("command", None)
        self._id = req['id'] = str(uuid.uuid1())
        self._info = req
        self.write_message("you are online " + req['name'])

    async def _on_update(self, req):
        """
        {"command": "update", "devices": [
            {"udid": "1232412312", "present": true}
        ]}
        """
        device_info = req['data']
        source_info = self._info.copy()
        source_info['updatedAt'] = time_now()
        device_info["sources"] = {
            self._id: source_info,
        }
        assert "udid" in device_info
        await db.device.save(device_info)

    async def on_message(self, message):
        req = json.loads(message)
        assert 'command' in req

        await getattr(self, "_on_"+req["command"])(req)

        """
        {"command": "ping"} // ping, update
        """
        logger.info("receive message: %s", message)

    def on_close(self):
        logger.info("websocket closed: %s", self.request.remote_ip)

        async def remove_source():
            def inner(q):
                return q.without({
                    "sources": {
                        self._id: True
                    }
                })

            await db.run(db.device.reql.replace(inner))
            # TODO(ssx): update present status

        IOLoop.current().add_callback(remove_source)
