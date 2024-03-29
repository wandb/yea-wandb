#!/usr/bin/env python

import logging
import netrc
import os
import random
import socket
import string
import subprocess
import sys
import time
import urllib
from typing import Any, Dict

import flask.cli

import requests

from .mitm import RelayControl

DUMMY_API_KEY = "1824812581259009ca9981580f8f8a9012409eee"

PLUGIN_DEFAULTS = {
    "mockserver-bind": "127.0.0.1",
    "mockserver-host": "localhost",
    "mockserver-relay": "",
    "mockserver-relay-remote-base-url": "https://api.wandb.ai",
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
        self._mitm_server = None

    def _get_ip(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]

    def _free_port(self, host):
        sock = socket.socket()
        sock.bind((host, 0))
        _, port = sock.getsockname()
        return port

    def _start_mitm_relay(self, base_url):
        from wandb.testing.relay import RelayServer

        flask.cli.show_server_banner = lambda *args: None
        inject = []
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)
        _relay_control = RelayControl()
        _relay_server = RelayServer(
            base_url=base_url, inject=inject, control=_relay_control
        )
        _relay_server.start()
        return _relay_server

    def _start_mitm(self):
        base_url = os.environ.get("WANDB_BASE_URL", "https://api.wandb.ai")
        api_key = os.environ.get("WANDB_API_KEY")

        if not api_key:
            netloc = urllib.parse.urlparse(base_url).netloc
            net = netrc.netrc()
            got = net.authenticators(netloc)
            user, account, passwd = got
            api_key = passwd

        self._mitm_server = self._start_mitm_relay(base_url)
        url = self._mitm_server.relay_url

        os.environ["WANDB_BASE_URL"] = url
        os.environ["WANDB_API_KEY"] = api_key
        # TODO: disable until the mitm server implements console stuff correctly
        os.environ["WANDB_CONSOLE"] = "off"
        os.environ["YEA_WANDB_MITM"] = url

    def _start_test_triggers(self, t):
        test_cfg = t._test_cfg

        trig_list = test_cfg.get("trigger", [])
        if not self._mitm_server:
            return

        mitm_control = self._mitm_server.relay_control
        if not mitm_control:
            return

        mitm_control.set_triggers(trig_list)

    def start_test(self, t):
        self._start_test_triggers(t)

    def start(self):
        if self._args.dryrun:
            return

        mockserver_bind = self._params["mockserver-bind"]
        mockserver_host = self._params["mockserver-host"]
        mockserver_relay = self._params["mockserver-relay"]
        mockserver_relay_remote_base_url = self._params[
            "mockserver-relay-remote-base-url"
        ]

        # TODO: mitm will eventually be default replacing mockserver and live mode
        if self._args.mitm:
            self._start_mitm()
            return

        # TODO: consolidate with github.com/wandb/client:tests/conftest.py

        # if we are using live mode. force mock_server plugin defaults
        if self._args.live:
            # This is causing issues, so lets not do it for now, localhost is safer
            # mockserver_bind = "0.0.0.0"
            # mockserver_host = "__auto__"
            mockserver_relay = "true"
            base_url = os.environ.get("WANDB_BASE_URL", "https://api.wandb.ai")
            mockserver_relay_remote_base_url = base_url

            # setup api key
            api_key = os.environ.get("WANDB_API_KEY")
            if not api_key:
                auth = requests.utils.get_netrc_auth(base_url)
                if not auth:
                    raise ValueError(
                        f"must configure api key by env or in netrc for {base_url}"
                    )
                api_key = auth[-1]
                os.environ["WANDB_API_KEY"] = api_key

        port = self._free_port(mockserver_bind)

        # get external ip
        if mockserver_host == "__auto__":
            mockserver_host = self._get_ip()

        root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        path = os.path.join(root, "mock_server.py")
        command = [sys.executable, "-u", path, "--yea"]
        env = os.environ
        env["PORT"] = str(port)
        env["PYTHONPATH"] = root
        env["MOCKSERVER_BIND"] = mockserver_bind
        if mockserver_relay:
            env["MOCKSERVER_RELAY"] = mockserver_relay
            env["MOCKSERVER_RELAY_REMOTE_BASE_URL"] = mockserver_relay_remote_base_url
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

        headers = {"Content-type": "application/json", "Accept": "application/json"}

        def get_ctx():
            return requests.get(server.base_url + "/ctx", headers=headers).json()

        def set_ctx(payload):
            return requests.put(
                server.base_url + "/ctx", json=payload, headers=headers
            ).json()

        def reset_ctx():
            return requests.delete(server.base_url + "/ctx", headers=headers).json()

        server.get_ctx = get_ctx
        server.set_ctx = set_ctx
        server.reset_ctx = reset_ctx

        server._port = port
        server.base_url = f"http://{mockserver_host}:{server._port}"
        self._server = server
        started = False
        for _ in range(30):
            try:
                res = requests.get(f"{server.base_url}/ctx", timeout=5, headers=headers)
                if res.status_code == 200:
                    started = True
                    break
                print(f"INFO: Attempting to connect but got: {res}")
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
            print(f"INFO: Mock server listing on {server._port}, see {logfname}")
        else:
            server.terminate()
            print(f"ERROR: Server failed to launch, see {logfname}")
            raise Exception("problem")

        os.environ["WANDB_BASE_URL"] = f"http://{mockserver_host}:{port}"
        if not mockserver_relay:
            os.environ["WANDB_API_KEY"] = DUMMY_API_KEY
        else:
            # os.environ["WANDB_BASE_URL"] = mockserver_relay_remote_base_url
            pass
        os.environ[
            "WANDB_SENTRY_DSN"
        ] = f"http://fakeuser@{mockserver_host}:{port}/5288891"

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
