import os
import pytest

from yea import cli
from yea import context
from yea import ytest
from yea_wandb import plugin


@pytest.fixture
def check_state_fn(mocked_yea_context):
    def fn(tname, state):
        print("TNAME", tname)
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        path = os.path.join(root, "tests", "configs", tname + ".yea")
        yc = mocked_yea_context
        t = ytest.YeaTest(tname=path, yc=yc)
        t._load()
        yp = plugin.YeaWandbPlugin(yc=yc)
        result_list = yp._check_state(t, state)
        return result_list

    yield fn


def test_single_run(check_state_fn):
    state = {}
    run1 = dict(config=dict(c1=1, c2=2), summary=dict(s1=1, s2=2), exitcode=0)
    runs = []
    runs.append(run1)
    state[":wandb:runs"] = runs
    state[":wandb:runs_len"] = len(runs)
    results = check_state_fn("single-run", state)
    assert not results


def test_contains_regex(check_state_fn):
    state = {}
    run0 = dict(config=dict(id=0), summary=dict(s=0), exitcode=0)
    runs = []
    runs.append(run0)
    state[":wandb:runs"] = runs
    state[":wandb:runs_len"] = len(runs)
    state[":wandb:runs"][0]["files"] = dict(asdf=dict(size=10), xboom=dict(size=20))
    results = check_state_fn("contains-regex-test", state)
    assert not results


def test_count_regex(check_state_fn):
    state = {}
    run0 = dict(config=dict(id=0), summary=dict(s=0), exitcode=0)
    runs = []
    runs.append(run0)
    state[":wandb:runs"] = runs
    state[":wandb:runs_len"] = len(runs)
    state[":wandb:runs"][0]["files"] = dict(asdf=dict(size=10), xboom=dict(size=20), 
            boomx=dict(size=40))
    results = check_state_fn("count-regex-test", state)
    assert not results


def test_find_test(check_state_fn):
    state = {}
    run0 = dict(config=dict(id=0), summary=dict(s=0), exitcode=0)
    run1 = dict(config=dict(id=1), summary=dict(s=1), exitcode=0)
    runs = []
    runs.append(run0)
    runs.append(run1)
    state[":wandb:runs"] = runs
    state[":wandb:runs_len"] = len(runs)
    results = check_state_fn("find-test", state)
    assert not results
