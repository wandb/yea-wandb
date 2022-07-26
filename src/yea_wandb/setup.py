import atexit
import functools
import importlib
import json
import os
import sys
import time
from collections import defaultdict
from typing import Dict, Optional

import yea._setup as ysetup

from . import hook


class ProfileItem:
    _num: int
    _elapsed: float
    _max: Optional[float]
    _min: Optional[float]

    def __init__(self):
        self._num = 0
        self._elapsed = 0
        self._max = None
        self._min = None

    def record(self, elapsed: float):
        self._num += 1
        self._elapsed += elapsed
        if self._max is None or elapsed > self._max:
            self._max = elapsed
        if self._min is None or elapsed < self._min:
            self._min = elapsed

    def __str__(self):
        return f"ProfileItem({self._num},{self._elapsed})"

    def get_data(self):
        d = dict(
            num=self._num,
            total=self._elapsed,
        )
        if self._num:
            d["mean"] = self._elapsed / self._num
            d["max"] = self._max
            d["min"] = self._min
        return d


class Profile:
    _data: Dict[str, ProfileItem]

    def __init__(self, file, items):
        self._file = file
        self._data = defaultdict(ProfileItem)
        self._items = items

    def record(self, fname: str, elapsed: float):
        # print(f"RECORD: {f} = {elapsed}")
        p = self._data[fname]
        p.record(elapsed)

    def write(self):
        with open(self._file, "w") as f:
            data = {}
            for k, v in self._data.items():
                # print(f"PROFILE {k}: {v}")
                data[k] = v.get_data()
            obj = json.dumps(data)
            f.write(obj)


def setup_plugin():
    yparams = ysetup._setup_params()
    names = os.environ.get("YEA_PLUGIN_WANDB_NAMES", "")
    values = os.environ.get("YEA_PLUGIN_WANDB_VALUES", "[]")
    names = names.split(",")
    # deal with empty names (it ends up being [""])
    if len(names) == 1 and not names[0]:
        names = []
    values = json.loads(values)
    for k, v in yparams.items():
        prefix = ":wandb:"
        if k.startswith(prefix):
            names.append(k[len(prefix) :])
            values.append(v)
    if not names or not values:
        return
    params = dict(zip(names, values))
    require = params.get("require")
    if require and require != "none":
        wandb = importlib.import_module("wandb")
        wandb.require(require)


def time_this(func, prof: Profile, tag: str):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        result = func(*args, **kwargs)
        end = time.monotonic()
        prof.record(tag or func.__name__, end - start)
        return result

    return wrapper


def setup_profile_wandb(prof: Profile):
    wandb = importlib.import_module("wandb")
    init_tag = ":wandb:init"
    log_tag = ":wandb:log"
    finish_tag = ":wandb:finish"
    if init_tag in prof._items:
        wandb.init = time_this(wandb.init, prof=prof, tag=init_tag)
    if log_tag in prof._items:
        wandb.sdk.wandb_run.Run.log = time_this(
            wandb.sdk.wandb_run.Run.log, prof=prof, tag=log_tag
        )
    if finish_tag in prof._items:
        wandb.sdk.wandb_run.Run.finish = time_this(
            wandb.sdk.wandb_run.Run.finish, prof=prof, tag=finish_tag
        )


def on_wandb_import(load_time: float, prof: Profile):
    import_tag = ":wandb:import"
    if import_tag in prof._items:
        prof.record(import_tag, elapsed=load_time)
    setup_profile_wandb(prof=prof)


def on_wandb_atexit(prof: Profile):
    prof.write()


def setup_profile():
    prof_data = ysetup._setup_profile()
    if not prof_data:
        return

    prof_file, prof_items = prof_data
    prof = Profile(file=prof_file, items=prof_items)

    atexit.register(on_wandb_atexit, prof=prof)
    if sys.modules.get("wandb"):
        setup_profile_wandb(prof=prof)

    hook.add_import_hook(
        "wandb", lambda load_time: on_wandb_import(load_time=load_time, prof=prof)
    )


def setup():
    setup_plugin()
    setup_profile()
