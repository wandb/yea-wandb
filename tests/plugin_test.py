
from yea_wandb import plugin

def test_this():
    result =  []
    yc = None
    yp = plugin.YeaWandbPlugin(yc=yc)
    exp = {"1": 1, "2": 2}
    act = {"1": 1, "2": 22}
    s = "something"
    yp._check_dict(result=result, s=s, expected=exp, actual=act)
    result = list(set(result))
    print("GOT result", result)
    assert len(result) == 1
