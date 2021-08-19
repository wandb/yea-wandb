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
assert:
  - :wandb:runs_len: 1
  - :wandb:runs[0][config]: {}
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
