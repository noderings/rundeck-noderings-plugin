"""Workflow step: start, stop or restart a NodeRings virtual machine."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nr_compute  # noqa: E402
import nr_rundeck  # noqa: E402
from nr_rundeck import config  # noqa: E402

WANT = {"start": "running", "stop": "stopped", "restart": "restarted"}


def power(client, env=None, out=None):
    name = config("hostname", None, env)
    action = config("action", None, env)
    if action not in WANT:
        raise nr_rundeck.StepFailure("action must be start, stop or restart")
    vm = nr_compute.find_vm(client, name or "")
    if not vm:
        raise nr_rundeck.StepFailure(f"no NodeRings virtual machine is named {name}")
    state = nr_compute.power_state(vm)
    if (action, state) in (("start", "running"), ("stop", "stopped")):
        print(f"{name} is already {state}.", file=out or sys.stdout)
        return vm
    vm = nr_compute.set_power(client, vm["id"], WANT[action], timeout=int(config("wait_timeout", "900", env)))
    print(f"{name} is {nr_compute.power_state(vm)}.", file=out or sys.stdout)
    return vm


def main():
    power(nr_rundeck.client())


if __name__ == "__main__":
    nr_rundeck.run(main)
