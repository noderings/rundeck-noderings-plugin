"""
Resource model source: lists the organization's NodeRings virtual machines as
Rundeck nodes, in Rundeck's JSON resource format.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nr_compute  # noqa: E402
import nr_rundeck  # noqa: E402


def to_node(vm, env=None):
    view = nr_compute.vm_view(vm)
    address = vm.get("ipv4") or vm.get("ipv6")
    tags = list(view["tags"])
    city = vm.get("regionCity")
    extra_tags = [t for t in ("noderings", view["power_state"], city, vm.get("planCode")) if t]
    attrs = {
        "nodename": vm.get("hostname"),
        "hostname": address,
        "username": nr_rundeck.config("username", "root", env),
        "osFamily": "unix",
        "osName": "Linux",
        "osVersion": view["distro"],
        "description": f"NodeRings {vm.get('planCode') or ''} in {city or ''}".strip(),
        "tags": ",".join(sorted(set(tags + [t.lower().replace(" ", "-") for t in extra_tags]))),
        "noderings-id": vm.get("id"),
        "noderings-distro": view["distro"],
        "noderings-power-state": view["power_state"],
        "noderings-plan": vm.get("planCode"),
        "noderings-provider": vm.get("providerName"),
        "noderings-country": vm.get("regionCountry"),
        "noderings-city": city,
        "noderings-ipv4": vm.get("ipv4"),
        "noderings-ipv6": vm.get("ipv6"),
        "noderings-firewall-ruleset-id": vm.get("firewallRulesetId"),
    }
    key_path = nr_rundeck.config("ssh_key_storage_path", None, env)
    if key_path:
        attrs["ssh-key-storage-path"] = key_path
    return {k: v for k, v in attrs.items() if v not in (None, "")}


def nodes(client, env=None):
    want_tags = set(nr_rundeck.config_list("tag_filter", env))
    running_only = nr_rundeck.config_bool("running_only", False, env)
    out = {}
    for vm in client.list_virtual_machines():
        view = nr_compute.vm_view(vm)
        if not vm.get("hostname") or not (vm.get("ipv4") or vm.get("ipv6")):
            continue
        if want_tags and not want_tags.issubset(set(view["tags"])):
            continue
        if running_only and view["power_state"] not in ("running", "created"):
            continue
        node = to_node(vm, env)
        out[node["nodename"]] = node
    return out


def main():
    print(json.dumps(nodes(nr_rundeck.client()), indent=2, sort_keys=True))


if __name__ == "__main__":
    nr_rundeck.run(main)
