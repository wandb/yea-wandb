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
        self._process_trigger(request, "pre")
        sig = self._signature(request)
        obj = self._controls[sig]
        # print("check", sig, obj._event.is_set())
        self._process_trigger(request, "post")
        obj.wait()
        # print("waitdone")

    def _process_trigger(self, request: "flask.Request", trig_type):
        sig = self._signature(request)
        service = sig
        trig_item = self._find_trigger(service)
        self._do_trigger(trig_item, trig_type)

    def _relay_set_active(self, sig, delay=None):
        obj = self._controls[sig]
        obj.set(delay=delay)
        # print("active", sig, delay)

    def _relay_set_paused(self, sig):
        obj = self._controls[sig]
        obj.clear()
        # print("pause", sig)

    def _relay_set_reset(self, sig, delay=None):
        # give a new control object for future requests
        self._controls[sig] = RelayControlObject()

    def _control_command(self, command, service, delay_time=None):
        # print("control", command, service, delay_time)
        if command == "pause":
            self._relay_set_paused(service)
        elif command == "unpause":
            self._relay_set_active(service)
        elif command == "reset":
            self._relay_set_reset(service)
        elif command == "delay":
            self._relay_set_paused(service)
            self._relay_set_active(service, delay=delay_time)

    def _find_trigger(self, service: str):
        trig_item = None
        for trig in self._triggers:
            trig_name = next(iter(trig))
            if trig_name != service:
                continue
            trig_item = trig[trig_name]
            break
        return trig_item

    def _do_trigger(self, trig_item, trig_type):
        if not trig_item:
            return
        command = trig_item.get("command")
        service = trig_item.get("service")
        delay_time = trig_item.get("time")
        one_shot = trig_item.get("one_shot")
        if delay_time:
            command = "delay"
        seen_count = trig_item.get("_seen_count", 0)
        trig_count = trig_item.get("_trig_count", 0)
        # print("seen count", seen_count)
        skip = trig_item.get("skip", 0)
        count = trig_item.get("count", 0)
        # TODO restructure code for count and skip
        ignore = False
        if skip and seen_count < skip:
            ignore = True
        if count and trig_count >= count:
            ignore = True
        # print("trigger", ignore, skip, count, trig_item)
        if trig_type in {"control", "pre"}:
            if not ignore:
                self._control_command(command, service, delay_time)
                trig_item["_trig_count"] = trig_count + 1
            trig_item["_seen_count"] = seen_count + 1

        # print("trig_type", trig_type, one_shot, trig_count)
        if trig_type == "post":
            if one_shot and trig_count:
                self._control_command("reset", service, delay_time)
                trig_item["one_shot"] = 0

    def control(self, request: "flask.Request"):
        request = flask.request
        request_data = request.get_json()
        command = request_data.get("command")
        service = request_data.get("service")
        delay_time = request_data.get("time")
        if command == "trigger":
            trig_item = self._find_trigger(service)
            self._do_trigger(trig_item, "control")
        else:
            self._control_command(command, service, delay_time)
        return {"hello": "there"}

    def set_triggers(self, trig_list):
        self._triggers = trig_list
