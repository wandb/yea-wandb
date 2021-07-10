"""wandb plugin for yea."""

from yea_wandb import backend
from yea_wandb.mock_server import ParseCTX  # noqa: E402


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

    def _check_state(self, t, state):
        test_cfg = t._test_cfg
        if not test_cfg:
            return
        if not self._backend._server:
            # we are live
            return
        ctx = self._backend.get_state()
        # print("GOT ctx", ctx)
        parsed = ParseCTX(ctx)
        print("DEBUG config", parsed.config)
        print("DEBUG summary", parsed.summary)
        result = []
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
            print("EXPECTED", exit, config, summary)

            ctx_config = parsed.config or {}
            ctx_config.pop("_wandb", None)
            ctx_summary = parsed.summary or {}
            for k in list(ctx_summary):
                if k.startswith("_"):
                    ctx_summary.pop(k)
            print("ACTUAL", "unkn", ctx_config, ctx_summary)

            if exit is not None:
                fs_list = ctx.get("file_stream")
                ctx_exit = fs_list[-1].get("exitcode")
                if exit != ctx_exit:
                    result.append("BAD_EXIT({}!={})".format(exit, ctx_exit))
            self._check_dict(result, "CONFIG", expected=config, actual=ctx_config)
            self._check_dict(result, "SUMMARY", expected=summary, actual=ctx_summary)

        return result

    def test_check(self, t):
        state = self._backend.get_state()
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
