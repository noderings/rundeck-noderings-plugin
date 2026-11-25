"""Workflow step: order a NodeRings virtual machine and wait until it is ready."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nr_compute  # noqa: E402
import nr_rundeck  # noqa: E402
from nr_rundeck import config, config_list, data  # noqa: E402


def create(client, env=None, out=None):
    hostname = config("hostname", None, env)
    if not hostname:
        raise nr_rundeck.StepFailure("hostname is required")
    existing = nr_compute.find_vm(client, hostname)
    if existing:
        if config("if_exists", "fail", env) == "fail":
            raise nr_rundeck.StepFailure(f"a virtual machine named {hostname} already exists ({existing['id']})")
        print(f"{hostname} already exists ({existing['id']}); nothing ordered.", file=out or sys.stdout)
        vm = existing
    else:
        plan_id, region_id = config("plan_id", None, env), config("region_id", None, env)
        if not (plan_id and region_id):
            plan, country, city = config("plan", None, env), config("country", None, env), config("city", None, env)
            if not (plan and country and city):
                raise nr_rundeck.StepFailure("give plan, country and city (or plan_id and region_id)")
            plan_id, region_id, offer = nr_compute.choose_offer(
                client, plan, country, city, billing_type=config("billing_type", "usage", env), sort=config("sort", "price", env)
            )
            print(f"Ordering {hostname}: {plan} from {offer['provider_name']} in {city}, {country}.", file=out or sys.stdout)
        keys = nr_compute.resolve_ssh_keys(client, config_list("ssh_keys", env))
        password = config("password", None, env)
        if not keys and not password:
            raise nr_rundeck.StepFailure("a new virtual machine needs ssh_keys or a root password")
        ruleset = config("firewall_ruleset", None, env)
        ruleset_id = nr_compute.resolve_ruleset(client, ruleset) if ruleset else None
        timeout = int(config("wait_timeout", "900", env))
        vm = nr_compute.order_vm(
            client,
            hostname,
            plan_id,
            region_id,
            distro=config("distro", "ubuntu_24_04", env),
            ssh_key_ids=keys,
            password=password,
            tags=config_list("tags", env),
            ruleset_id=ruleset_id,
            wait=True,
            timeout=timeout,
        )
    view = nr_compute.vm_view(vm)
    print(f"{hostname} is {view['power_state']} at {vm.get('ipv4') or vm.get('ipv6')} ({vm['id']}).", file=out or sys.stdout)
    data("noderings_vm_id", vm.get("id"), out)
    data("noderings_ipv4", vm.get("ipv4"), out)
    data("noderings_ipv6", vm.get("ipv6"), out)
    return vm


def main():
    create(nr_rundeck.client())


if __name__ == "__main__":
    nr_rundeck.run(main)
