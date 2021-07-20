"""wandb plugin for yea."""

import re

from yea_wandb import backend
from yea_wandb.mock_server import ParseCTX  # noqa: E402


def parse_term(v, state, result=None):
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
ops = {
    "<": "__lt__",
    "<=": "__le__",
    ">": "__gt__",
    ">=": "__gt__",
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
        opfunc = ops.get(op)
        if not opfunc:
            result.append("unknown op: {}".format(op))
            return
        assert len(v) == 2, "ops need 2 parameters"
        v1 = parse_term(v[0], state, result)
        v2 = parse_term(v[1], state, result)
        f = getattr(v1, opfunc, None)
        if f is None:
            result.append("unimplemented op: {}".format(opfunc))
            return
        if not f(v2):
            print("invalid", k, v1, op, v2)
            result.append("ASSERT {}: {} {} {}".format(k, v1, op, v2))
        return
    # if not isinstance(v, (str, int, float)):
    #     print("WARNING: Not sure how to parse (might be ok)")
    k = parse_term(k, state, result)
    v = parse_term(v, state, result)
    if k != v:
        print("unequal", k, v)
        result.append("{} != {}".format(k, v))


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

    def _check_dict(self, result, s, expected, actual):
        if expected is None:
            return
        for k, v in actual.items():
            exp = expected.get(k)
            if exp != v:
                result.append("BAD_{}({}:{}!={})".format(s, k, exp, v))
        for k, v in expected.items():
            act = actual.get(k)
            if v != act:
                result.append("BAD_{}({}:{}!={})".format(s, k, v, act))

    def _get_backend_state(self):
        if not self._backend._server:
            # we are live
            return
        ctx = self._backend.get_state()
        parsed = ParseCTX(ctx)
        # print("DEBUG config", parsed.config)
        # print("DEBUG summary", parsed.summary)
        state = {}
        run = {}
        run["config"] = parsed.config
        run["summary"] = parsed.summary

        # TODO: move to ParseCTX
        ctx_exitcode = None
        fs_list = ctx.get("file_stream")
        if fs_list:
            ctx_exitcode = fs_list[-1].get("exitcode")
            run["exitcode"] = ctx_exitcode

        runs = []
        runs.append(run)
        state[":wandb:runs"] = runs
        state[":wandb:runs_len"] = len(runs)

        # TODO: remove this eventually
        state["config"] = parsed.config
        state["summary"] = parsed.summary
        if ctx_exitcode is not None:
            state["exitcode"] = ctx_exitcode
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
                    print("DEFINE :{}={}".format(k, val))

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

        wandb_check = test_cfg.get("check-ext-wandb")
        if not wandb_check:
            return result
        runs = wandb_check.get("run")

        if runs is not None:
            # only support one run right now
            assert len(runs) == 1
            run = runs[0]
            config = run.get("config")
            exit = run.get("exit")
            summary = run.get("summary")
            ignore_extra_config_keys = run.get("ignore_extra_config_keys")
            ignore_extra_summary_keys = run.get("ignore_extra_summary_keys")
            print("EXPECTED", exit, config, summary)

            ctx_config = state.get("config") or {}
            ctx_config.pop("_wandb", None)

            # if we are ignoring config keys that are present in the
            # actual but not enumerated in the expected, we need to
            # prune the actual down to just the keys that overlap
            # with the expected
            if ignore_extra_config_keys:
                actual_config_keys = list(ctx_config.keys())
                for key in actual_config_keys:
                    if key not in config:
                        del ctx_config[key]

            ctx_summary = state.get("summary") or {}
            for k in list(ctx_summary):
                if k.startswith("_"):
                    ctx_summary.pop(k)

            if ignore_extra_summary_keys:
                actual_summary_keys = list(ctx_summary.keys())
                for key in actual_summary_keys:
                    if key not in summary:
                        del ctx_summary[key]

            print("ACTUAL", "unkn", ctx_config, ctx_summary)

            if exit is not None:
                ctx_exit = state.get("exitcode")
                if exit != ctx_exit:
                    result.append("BAD_EXIT({}!={})".format(exit, ctx_exit))

            self._check_dict(result, "CONFIG", expected=config, actual=ctx_config)
            self._check_dict(result, "SUMMARY", expected=summary, actual=ctx_summary)

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
