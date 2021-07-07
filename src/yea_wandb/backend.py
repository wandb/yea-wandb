#!/usr/bin/env python

import os
import socket
import subprocess
import sys
import time

import requests

DUMMY_API_KEY = "1824812581259009ca9981580f8f8a9012409eee"


class Backend:
    def __init__(self, args):
        self._args = args
        self._server = None

    def _free_port(self):
        sock = socket.socket()
        sock.bind(("", 0))
        _, port = sock.getsockname()
        return port

    def start(self):
        if self._args.dryrun:
            return
        if self._args.live:
            return
        # TODO: consolidate with github.com/wandb/client:tests/conftest.py
        port = self._free_port()
        # root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
        # path = os.path.join(root, "tests", "utils", "mock_server.py")
        root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        path = os.path.join(root, "mock_server.py")
        command = [sys.executable, "-u", path]
        env = os.environ
        env["PORT"] = str(port)
        env["PYTHONPATH"] = root
        worker_id = 1
        logfname = os.path.join(
            "/tmp",
            "standalone-live_mock_server-{}.log".format(worker_id),
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
        server.base_url = "http://localhost:%i" % server._port
        self._server = server
        started = False
        for _ in range(30):
            try:
                res = requests.get("%s/ctx" % server.base_url, timeout=5)
                if res.status_code == 200:
                    started = True
                    break
                print("Attempting to connect but got: %s" % res)
            except requests.exceptions.RequestException:
                print(
                    "Timed out waiting for server to start...",
                    server.base_url,
                    time.time(),
                )
                if server.poll() is None:
                    time.sleep(1)
                else:
                    raise ValueError("Server failed to start.")
        if started:
            print("Mock server listing on {} see {}".format(server._port, logfname))
        else:
            server.terminate()
            print("Server failed to launch, see {}".format(logfname))
            raise Exception("problem")

        os.environ["WANDB_BASE_URL"] = "http://127.0.0.1:{}".format(port)
        os.environ["WANDB_API_KEY"] = DUMMY_API_KEY

    def reset(self):
        if not self._server:
            return
        self._server.reset_ctx()

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
