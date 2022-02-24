#!/usr/bin/env python

import os
import random
import socket
import string
import subprocess
import sys
import time
from typing import Any, Dict

import requests

DUMMY_API_KEY = "1824812581259009ca9981580f8f8a9012409eee"

PLUGIN_DEFAULTS = {
    "mockserver-bind": "127.0.0.1",
    "mockserver-host": "localhost",
}


def parse_plugin_args(defaults: Dict, cli_args: Any) -> Dict:
    plugin_args = {}
    plugin_args.update(defaults)
    # TODO: we have this somewhere else im sure
    prefix = "wandb:"
    for arg in cli_args.plugin_args:
        if not arg.startswith(prefix):
            continue
        arg = arg[len(prefix) :]
        if "=" not in arg:
            raise ValueError(f"Expecting key=value in {arg}")
        k, v = arg.split("=", 1)
        if k not in defaults:
            raise ValueError(f"Unknown plugin key {k}")
        plugin_args[k] = v
    return plugin_args


class Backend:
    def __init__(self, yc, args):
        self._yc = yc
        self._args = args
        self._server = None
        self._params = parse_plugin_args(PLUGIN_DEFAULTS, self._yc._args)

    def _free_port(self, host):
        sock = socket.socket()
        sock.bind((host, 0))
        _, port = sock.getsockname()
        return port

    def start(self):
        if self._args.dryrun:
            return
        if self._args.live:
            return
        mockserver_bind = self._params["mockserver-bind"]
        mockserver_host = self._params["mockserver-host"]
        # TODO: consolidate with github.com/wandb/client:tests/conftest.py
        port = self._free_port(mockserver_bind)
        root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        path = os.path.join(root, "mock_server.py")
        command = [sys.executable, "-u", path, "--yea"]
        env = os.environ
        env["PORT"] = str(port)
        env["PYTHONPATH"] = root
        env["MOCKSERVER_BIND"] = mockserver_bind
        worker_id = 1
        logfname = os.path.join(
            self._yc._cfg._cfroot,
            ".yea_cache",
            f"standalone-live_mock_server-{worker_id}.log",
        )
        logfile = open(logfname, "w")
        server = subprocess.Popen(
            command,
            stdout=logfile,
            env=env,
            stderr=subprocess.STDOUT,
            bufsize=1,
            close_fds=True,
        )

        def get_ctx():
            return requests.get(server.base_url + "/ctx").json()

        def set_ctx(payload):
            return requests.put(server.base_url + "/ctx", json=payload).json()

        def reset_ctx():
            return requests.delete(server.base_url + "/ctx").json()

        server.get_ctx = get_ctx
        server.set_ctx = set_ctx
        server.reset_ctx = reset_ctx

        server._port = port
        server.base_url = f"http://{mockserver_host}:{server._port}"
        self._server = server
        started = False
        for _ in range(30):
            try:
                res = requests.get(f"{server.base_url}/ctx", timeout=5)
                if res.status_code == 200:
                    started = True
                    break
                print("INFO: Attempting to connect but got: %s" % res)
            except requests.exceptions.RequestException:
                print(
                    "INFO: Timed out waiting for server to start...",
                    server.base_url,
                    time.time(),
                )
                if server.poll() is None:
                    time.sleep(1)
                else:
                    raise ValueError("Server failed to start.")
        if started:
            print("INFO: Mock server listing on {} see {}".format(server._port, logfname))
        else:
            server.terminate()
            print("ERROR: Server failed to launch, see {}".format(logfname))
            raise Exception("problem")

        os.environ["WANDB_BASE_URL"] = f"http://{mockserver_host}:{port}"
        os.environ["WANDB_API_KEY"] = DUMMY_API_KEY
        os.environ["WANDB_SENTRY_DSN"] = f"http://fakeuser@{mockserver_host}:{port}/5288891"

    # update the mock server context with the new values
    def update_ctx(self, ctx):
        if self._server is None:
            return
        print("INFO: Updating mock server context with: ", ctx)
        self._server.set_ctx(ctx)

    def reset(self):
        if not self._server:
            return
        self._server.reset_ctx()
        tmp_ctx = self._server.get_ctx()
        letters = string.ascii_letters

        emulate_str = "".join(random.choice(letters) for i in range(10))
        tmp_ctx["emulate_artifacts"] = emulate_str
        self._server.set_ctx(tmp_ctx)

    def get_state(self):
        if not self._server:
            return
        ret = self._server.get_ctx()
        return ret

    def stop(self):
        if not self._server:
            return
        self._server.terminate()
        self._server = None
