# yea-wandb

TODO: document!

Example:
```
id: 0.0.1
name: example test
tag:
  suite: nightly
env:
  - this: that
command:
  timeout: 3
  program: proc.py  # this defaults to the basename of yea file + ".py"
  args:
    - param1
    - param2
plugin:
  - wandb
depend:
  requirements:
    - wandb
  files:
    - file: this.txt
      source: https://raw.githubusercontent.com/wandb/wandb-testing/master/README.md
var:
  - runs_len:
      :fn:len: :wandb:runs
  - run0:
      :fn:find:
      - item
      - :wandb:runs
      - :item[config][id]: 0
assert:
  - :runs_len: 1
  - :op:contains:
    - :run0[telemetry][3]  # feature
    - 8  # keras
  - :wandb:runs_len: 1
  - :wandb:runs[0][config]: {id: 0}
  - :wandb:runs[0][summary]:
      m1: 1
      m2: 2
  - :wandb:runs[0][exitcode]: 0
parametrize:
  permute:
    - :yea:start_method:
      - fork
      - spawn
      - forkserver
```
