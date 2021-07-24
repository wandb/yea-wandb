"""wandb plugin for yea."""

import re

from yea_wandb import backend
from yea_wandb.mock_server import ParseCTX  # noqa: E402


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


FNSTR = ":fn:"
FNS = {
    "find": fn_find,
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
    found = state.get(var)
    if found is None:
        print("WARNING: Variable `{}` not found in state keys: {}".format(var, ",".join(state.keys())))
        return None
    for ind in ind_list:
        if isinstance(found, list):
            ind = int(ind)
            if ind < 0 or ind >= len(found):
                bad = "index {} not found in {} [{}]".format(ind, var, ",".join(ind_list))
                if result is not None:
                    result.append("Not found: " + bad)
                print("WARNING:", bad)
                return None
            lookup = found[ind]
        else:
            lookup = found.get(ind)
        if lookup is None:
            bad = "key {} not found in {} [{}]".format(ind, var, ",".join(ind_list))
            if result is not None:
                result.append("Not found: " + bad)
            print("WARNING:", bad)
            return None
        found = lookup
    return found


OPSTR = ":op:"
OPS = {
    "<": "__lt__",
    "<=": "__le__",
    ">": "__gt__",
    ">=": "__ge__",
    "==": "__eq__",
    "!=": "__ne__",
}


def parse_expr(adict, state, result):
    assert len(adict.keys()) == 1
    k = next(iter(adict))
    v = adict[k]
    # might be an op
    if isinstance(k, str) and k.startswith(OPSTR) and isinstance(v, list):
        op = k[len(OPSTR) :]
        opfunc = OPS.get(op)
        if not opfunc:
            result.append("unknown op: {}".format(op))
            return not result
        assert len(v) == 2, "ops need 2 parameters"
        v1 = parse_term(v[0], state, result)
        v2 = parse_term(v[1], state, result)
        f = getattr(v1, opfunc, None)
        if f is None:
            result.append("unimplemented op: {}".format(opfunc))
            return not result
        if not f(v2):
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
        self._backend = backend.Backend(args=self._yc._args)

    def monitors_start(self):
        self._backend.start()

    def monitors_stop(self):
        self._backend.stop()

    def monitors_reset(self):
        self._backend.reset()

    def _get_backend_state(self):
        if not self._backend._server:
            # we are live
            return

        state = {}
        runs = []

        glob_ctx = self._backend.get_state()
        glob_parsed = ParseCTX(glob_ctx)

        run_ids = glob_parsed.run_ids
        for run_id in run_ids:
            parsed = ParseCTX(glob_ctx, run_id)
            run = {}
            run["config"] = parsed.config_user
            run["summary"] = parsed.summary_user
            run["exitcode"] = parsed.exit_code
            runs.append(run)

        state[":wandb:runs"] = runs
        state[":wandb:runs_len"] = len(runs)

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

    def test_check(self, t):
        state = self._get_backend_state()
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
