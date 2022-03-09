"""wandb plugin for yea."""

import pprint
import re
from typing import Any, Dict, Optional

from yea_wandb import backend


def fn_find(args, state):
    assert isinstance(args, list)
    assert len(args) == 3
    var, data, expr = args

    pstate = state.copy()
    err = []
    d = parse_term(data, state=state, result=err)
    assert not err
    for item in d:
        pstate[":" + var] = item
        perr = []
        b = parse_expr(expr, state=pstate, result=perr)
        # if perr:
        #   print("GOT: err=, err)
        if b:
            return item
    return None


def fn_count_regex(args, state):
    assert isinstance(args, list)
    assert len(args) == 3
    var, data, pattern = args
    err = []
    d = parse_term(data, state=state, result=err)
    assert not err

    i = 0
    for item in d:
        if contains_regex([item], pattern):
            i += 1
    return i


def fn_len(args, state):
    var = args
    assert isinstance(var, str)
    err = []
    lst = parse_term(var, state=state, result=err)
    assert not err
    assert isinstance(lst, list)
    return len(lst)


def fn_keys(args, state):
    var = args
    assert isinstance(var, str)
    err = []
    dct = parse_term(var, state=state, result=err)
    assert not err
    assert isinstance(dct, dict)
    return list(sorted(dct.keys()))


def fn_sort(args, state):
    var = args
    assert isinstance(var, str)
    err = []
    lst = parse_term(var, state=state, result=err)
    assert not err
    assert isinstance(lst, list)
    return list(sorted(lst))


def fn_concat(args, state):
    assert isinstance(args, list)
    err = []
    lst = []
    for orig in args:
        item = parse_term(orig, state=state, result=err)
        lst.append(item)
    assert not err
    return "".join(lst)


def fn_sum(args, state):
    assert isinstance(args, str)  # name of array to sum over
    err = []
    lst = parse_term(args, state=state, result=err)
    assert not err
    return sum(lst)


FNSTR = ":fn:"
FNS = {
    "find": fn_find,
    "len": fn_len,
    "keys": fn_keys,
    "sort": fn_sort,
    "count_regex": fn_count_regex,
    "concat": fn_concat,
    "sum": fn_sum,
}


def parse_term(v, state, result=None):
    # fn support: only handle single key dict that begins with :fn:
    if isinstance(v, dict) and len(v) == 1:
        k = next(iter(v))
        if isinstance(k, str) and k.startswith(FNSTR):
            fn = k[len(FNSTR) :]
            fnfunc = FNS.get(fn)
            return fnfunc(v[k], state=state)
    if not isinstance(v, str):
        return v
    if v.startswith("::"):
        v = v[1:]
        return v
    if not v.startswith(":"):
        return v
    spl = v.split("[", 1)
    var = spl[0]
    ind_list = []
    if len(spl) == 2:
        ind_list = re.findall(r"\[([^[\]]*)\]", "[" + spl[1])
    if var not in state:
        print(
            "WARNING: Variable `{}` not found in state keys: {}".format(
                var, ",".join(state.keys())
            )
        )
        return None
    found = state.get(var)
    for ind in ind_list:
        if isinstance(found, list):
            ind = int(ind)
            if ind < 0 or ind >= len(found):
                bad = "index {} not found in {} [{}]".format(
                    ind, var, ",".join(ind_list)
                )
                if result is not None:
                    result.append("Not found: " + bad)
                print("WARNING:", bad)
                return None
            lookup = found[ind]
        else:
            if ind not in found:
                bad = "key {} not found in {} [{}]".format(ind, var, ",".join(ind_list))
                if result is not None:
                    result.append("Not found: " + bad)
                print("WARNING:", bad)
                return None
            lookup = found.get(ind)
        found = lookup
    return found


def contains_regex(iterable, pattern):
    """
    v1: Iterable[Str], i.e Dict[Str --> Any], List[Str], etc.
    v2: Str
    """
    for s in iterable:
        if re.search(pattern, s):
            return True


OPSTR = ":op:"
OPS = {
    "<": "__lt__",
    "<=": "__le__",
    ">": "__gt__",
    ">=": "__ge__",
    "==": "__eq__",
    "!=": "__ne__",
    "contains": "__contains__",
    "not_contains": "__contains__",
}
OPS_FUNCS = {
    "contains_regex": contains_regex,
    "not_contains_regex": contains_regex,
}


def parse_expr(adict, state, result):
    assert len(adict.keys()) == 1
    k = next(iter(adict))
    v = adict[k]
    # might be an op
    if isinstance(k, str) and k.startswith(OPSTR) and isinstance(v, list):
        op = k[len(OPSTR) :]
        opfunc = OPS.get(op) or OPS_FUNCS.get(op)
        if not opfunc:
            result.append("unknown op: {}".format(op))
            return not result
        assert len(v) == 2, "ops need 2 parameters"
        v1 = parse_term(v[0], state, result)
        v2 = parse_term(v[1], state, result)
        if op in OPS_FUNCS:
            f = OPS_FUNCS.get(op)
            b = f(v1, v2)
        else:
            f = getattr(v1, opfunc, None)
            if f is None:
                result.append("unimplemented op: {}".format(opfunc))
                return not result
            b = f(v2)
        # hack to invert result for not_contains
        if op.startswith("not_"):
            b = not (b)
        if not b:
            print("invalid", k, v1, op, v2)
            result.append("ASSERT {}: {} {} {}".format(k, v1, op, v2))
        return not result
    # if not isinstance(v, (str, int, float)):
    #     print("WARNING: Not sure how to parse (might be ok)")
    v1 = parse_term(k, state, result)
    v2 = parse_term(v, state, result)
    if v1 != v2:
        # print("ERROR: Unequal", k, v1, v2)
        result.append("ASSERT {}: {} != {}".format(k, v1, v2))
    return not result


# TODO: derive from YeaPlugin
class YeaWandbPlugin:
    def __init__(self, yc):
        self._yc = yc
        self._backend = None
        self._name = "wandb"

    def monitors_init(self):
        self._backend = backend.Backend(yc=self._yc, args=self._yc._args)

    def monitors_start(self):
        self._backend.start()

    def monitors_configure(self, config: Optional[Dict[str, Any]]):
        if config is None:
            return
        # optionally configure backend (update context)
        ctx = config.get("mock_server")
        if ctx is not None:
            self._backend.update_ctx(ctx)

    def monitors_stop(self):
        self._backend.stop()

    def monitors_reset(self):
        self._backend.reset()

    def _get_backend_state(self, debug=False, ytest=None):
        if not self._backend._server:
            # we are live
            return

        from yea_wandb.mock_server import ParseCTX  # noqa: E402

        state = {}
        runs = []

        glob_ctx = self._backend.get_state()
        glob_parsed = ParseCTX(glob_ctx)
        ddict = {"global": glob_parsed._debug()}

        run_ids = glob_parsed.run_ids
        for run_id in run_ids:
            parsed = ParseCTX(glob_ctx, run_id)
            ddict.update({run_id: parsed._debug()})
            run = {}
            run["run_id"] = parsed.run_id
            run["config"] = parsed.config_user
            run["config_wandb"] = parsed.config_wandb
            run["history"] = parsed.history
            run["summary"] = parsed.summary_user
            run["summary_wandb"] = parsed.summary_wandb
            run["telemetry"] = parsed.telemetry
            run["metrics"] = parsed.metrics
            run["exitcode"] = parsed.exit_code
            run["files"] = parsed.files
            run["output"] = parsed.output
            run["git"] = parsed.git
            run["alerts"] = parsed.alerts
            run["tags"] = parsed.tags
            run["notes"] = parsed.notes
            run["group"] = parsed.group
            run["job_type"] = parsed.job_type
            run["name"] = parsed.name
            run["program"] = parsed.program
            run["host"] = parsed.host
            runs.append(run)

        state[":wandb:artifacts"] = glob_parsed.artifacts
        state[":wandb:portfolio_links"] = glob_parsed.portfolio_links
        state[":wandb:sentry_events"] = glob_parsed.sentry_events
        state[":wandb:runs"] = runs
        # deprecate this
        state[":wandb:runs_len"] = len(runs)

        # TODO(): yea should actually have its own checks, for now do it here
        if ytest:
            state[":yea:exit"] = ytest._retcode

        if debug:
            pp = pprint.PrettyPrinter(indent=2)
            # pp.pprint(ddict)
            pp.pprint(state)

        return state

    def _check_vars(self, t, state):
        test_cfg = t._test_cfg

        vars_list = test_cfg.get("var")
        if vars_list is None:
            return

        for vdict in vars_list:
            for k, v in vdict.items():
                val = parse_term(v, state)
                if val is not None:
                    state[":" + k] = val
                    # print("DEFINE :{}={}".format(k, val))

    def _check_asserts(self, t, state, result):
        test_cfg = t._test_cfg

        assert_list = test_cfg.get("assert")
        if assert_list is None:
            return

        for a in assert_list:
            parse_expr(a, state, result)

    def _check_state(self, t, state):
        test_cfg = t._test_cfg
        if not test_cfg:
            return

        self._check_vars(t, state)

        result = []
        self._check_asserts(t, state, result)

        result = list(set(result))
        return result

    def test_check(self, t, debug=False):
        state = self._get_backend_state(debug=debug, ytest=t)
        result_list = None
        if state:
            result_list = self._check_state(t, state)
        return result_list

    def test_prep(self, t):
        pass

    def test_done(self, t):
        pass

    @property
    def name(self):
        return self._name


def init_plugin(yc):
    plug = YeaWandbPlugin(yc)
    return plug
