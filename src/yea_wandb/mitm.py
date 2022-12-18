# type: ignore

import threading
from collections import defaultdict

import flask


class RelayControlObject:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._event.set()
        self._thread = None

    def set(self, delay=None) -> None:
        if not delay:
            self._event.set()
            return
        delayed_call = threading.Timer(delay, self.set)
        self._thread = delayed_call
        delayed_call.start()

    def clear(self) -> None:
        self._event.clear()

    def wait(self) -> None:
        self._event.wait()


class RelayControl:
    def __init__(self) -> None:
        self._controls = defaultdict(RelayControlObject)
        self._triggers = []

    def _signature(self, request: "flask.Request"):
        endpoint = request.path.split("/")[-1]
        return endpoint

    def process(self, request: "flask.Request"):
        sig = self._signature(request)
        obj = self._controls[sig]
        # print("check", sig, obj._event.is_set())
        obj.wait()
        # print("waitdone")

    def _relay_set_active(self, sig, delay=None):
        obj = self._controls[sig]
        obj.set(delay=delay)
        # print("active", sig, delay)

    def _relay_set_paused(self, sig):
        obj = self._controls[sig]
        obj.clear()
        # print("pause", sig)

    def _control_command(self, command, service, delay_time=None):
        if command == "pause":
            self._relay_set_paused(service)
        elif command == "unpause":
            self._relay_set_active(service)
        elif command == "delay":
            self._relay_set_paused(service)
            self._relay_set_active(service, delay=delay_time)

    def control(self, request: "flask.Request"):
        request = flask.request
        request_data = request.get_json()
        command = request_data.get("command")
        service = request_data.get("service")
        delay_time = request_data.get("time")
        if command == "trigger":
            trig_item = None
            for trig in self._triggers:
                trig_name = next(iter(trig))
                if trig_name != service:
                    continue
                trig_item = trig[trig_name]
                break
            # print("GOT", trig_item)
            if trig_item:
                command = trig_item.get("command")
                service = trig_item.get("service")
                delay_time = trig_item.get("time")
                if delay_time:
                    command = "delay"
                seen_count = trig_item.get("_seen_count", 0)
                trig_count = trig_item.get("_trig_count", 0)
                skip = trig_item.get("skip", 0)
                count = trig_item.get("count", 0)
                # TODO restructure code for count and skip
                ignore = False
                if skip and seen_count < skip:
                    ignore = True
                if count and trig_count >= count:
                    ignore = True
                # print("trigger", ignore, skip, count, trig_item)
                if not ignore:
                    self._control_command(command, service, delay_time)
                    trig_item["_trig_count"] = trig_count + 1
                trig_item["_seen_count"] = seen_count + 1
        else:
            self._control_command(command, service, delay_time)
        return {"hello": "there"}

    def set_triggers(self, trig_list):
        self._triggers = trig_list
