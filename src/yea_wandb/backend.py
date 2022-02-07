#!/usr/bin/env python

import os
import random
import socket
import string
import subprocess
import sys
import time

import requests

DUMMY_API_KEY = "1824812581259009ca9981580f8f8a9012409eee"


class Backend:
    def __init__(self, yc, args):
        self._yc = yc
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
        root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        path = os.path.join(root, "mock_server.py")
        command = [sys.executable, "-u", path, "--yea"]
        env = os.environ
        env["PORT"] = str(port)
        env["PYTHONPATH"] = root
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
        server.base_url = f"http://localhost:{server._port}"
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

        os.environ["WANDB_BASE_URL"] = f"http://127.0.0.1:{port}"
        os.environ["WANDB_API_KEY"] = DUMMY_API_KEY
        os.environ["WANDB_SENTRY_DSN"] = f"http://fakeuser@127.0.0.1:{port}/5288891"

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
