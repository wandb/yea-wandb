import argparse
import sys
from typing import Callable, List, Optional

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal

import pytest

from yea.cli import CliArgs, cli_list, cli_run
from yea.context import YeaContext


# Borrowed from wandb/yea:tests/conftest.py
def default_cli_args(
    action: Literal["run", "r", "list", "l"] = "run",
    all: bool = False,
    debug: bool = False,
    yeadoc: bool = False,
    dryrun: bool = False,
    func: Optional[Callable] = None,
    live: Optional[bool] = False,
    platform: Optional[str] = None,
    shard: Optional[str] = None,
    suite: Optional[str] = None,
    tests: Optional[List[str]] = None,
    plugin_args: Optional[list] = None,
    strict: Optional[bool] = False,
    noskip: Optional[bool] = False,
) -> dict:
    return {
        "action": action,
        "all": all,
        "debug": debug,
        "yeadoc": yeadoc,
        "dryrun": dryrun,
        "func": func if func is not None else cli_run if action in ("run", "r") else cli_list,
        "live": live,
        "platform": platform,
        "shard": shard,
        "suite": suite,
        "tests": tests,
        "plugin_args": plugin_args,
        "strict": strict,
        "noskip": noskip,
    }


@pytest.fixture
def mocked_yea_context(request):
    params = getattr(request, "params", {})
    cli_args = default_cli_args(**params)
    args = CliArgs(argparse.Namespace(**cli_args))

    yield YeaContext(args=args)
