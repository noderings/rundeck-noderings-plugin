"""Workflow step: delete a NodeRings virtual machine."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nr_compute  # noqa: E402
import nr_rundeck  # noqa: E402
from nr_client import Waiter, is_not_found  # noqa: E402
from nr_rundeck import config  # noqa: E402


def delete(client, env=None, out=None):
    name = config("hostname", None, env)
    vm = nr_compute.find_vm(client, name or "")
    if not vm:
        if nr_rundeck.config_bool("fail_if_missing", False, env):
            raise nr_rundeck.StepFailure(f"no NodeRings virtual machine is named {name}")
        print(f"{name} does not exist; nothing to delete.", file=out or sys.stdout)
        return False

    def call():
        try:
            client.delete_virtual_machine(vm["id"])
        except Exception as exc:  # pylint: disable=broad-except
            if not is_not_found(exc):
                raise
        return True

    Waiter(int(config("wait_timeout", "900", env))).retry_busy(call)
    print(f"Deleted {name} ({vm['id']}).", file=out or sys.stdout)
    return True


def main():
    delete(nr_rundeck.client())


if __name__ == "__main__":
    nr_rundeck.run(main)
