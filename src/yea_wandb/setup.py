import importlib
import json
import os

import yea._setup as ysetup


def setup_plugin():
    wandb = importlib.import_module("wandb")

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
        wandb.require(require)


def setup():
    setup_plugin()
