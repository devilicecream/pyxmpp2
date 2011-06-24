#
# (C) Copyright 2011 Jacek Konieczny <jajcus@jajcus.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License Version
# 2.1 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# pylint: disable-msg=W0201

"""PyXMPP events."""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

import Queue
import threading
import logging
import inspect

from collections import defaultdict

logger = logging.getLogger("pyxmpp.mainloop.events")

from .interfaces import Event, EventHandler, QUIT
from ..settings import XMPPSettings

def event_queue_factory(settings):
    return Queue.Queue(settings["event_queue_max_size"])

class EventDispatcher(object):
    def __init__(self, settings = None, handlers = None):
        if settings is None:
            settings = XMPPSettings()
        self.queue = settings["event_queue"]
        self._handlers_map = defaultdict(list)
        if handlers:
            self.handlers = list(handlers)
        else:
            self.handlers = []
        self._update_handlers()
        self.lock = threading.RLock()

    def add_handler(self, handler):
        if not isinstance(handler, EventHandler):
            raise TypeError, "Not an EventHandler"
        with self.lock:
            if handler in self.handlers:
                return
            self.handlers.append(handler)
            self._update_handlers()

    def remove_handler(self, handlers):
        with self.lock:
            if handler in self.handlers:
                self.handlers.remove(handler)
                self._update_handlers()

    def _update_handlers(self):
        handler_map = defaultdict(list)
        for i, obj in enumerate(self.handlers):
            for name, handler in inspect.getmembers(obj, callable):
                if not hasattr(handler, "_pyxmpp_event_handled"):
                    continue
                # pylint: disable-msg=W0212
                event_class = handler._pyxmpp_event_handled
                handler_map[event_class].append( (i, handler) )
        self._handler_map = handler_map

    def dispatch(self, block = False, timeout = None):
        logger.debug(" dispatching...")
        try:
            event = self.queue.get(block, timeout)
        except Queue.Empty:
            logger.debug("    queue empty")
            return None
        try:
            logger.debug("    event: {0!r}".format(event))
            if event is QUIT:
                return QUIT
            handlers = list(self._handler_map[None])
            klass = event.__class__
            if klass in self._handler_map:
                handlers += self._handler_map[klass]
            logger.debug("    handlers: {0!r}".format(handlers))
            handlers.sort() # to restore the original order of handler objects
            for dummy, handler in handlers:
                logger.debug(u"  passing the event to: {0!r}".format(handler))
                if handler(event) and event is not QUIT:
                    return event
            return event
        finally:
            self.queue.task_done()

    def flush(self, dispatch = True):
        if dispatch:
            while True:
                event = self.dispatch(False)
                if event in (None, QUIT):
                    return event
        else:
            while True:
                try:
                    self.queue.get(False)
                except Queue.Empty:
                    return None

    def loop(self):
        while self.dispatch(True) is not QUIT:
            pass

XMPPSettings.add_defaults({
                            u"event_queue_max_size": None, 
                            })
XMPPSettings.add_default_factory("event_queue", event_queue_factory, True)
