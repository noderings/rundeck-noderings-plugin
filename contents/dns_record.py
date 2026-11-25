"""Workflow step: set or delete the records of one name and type in a NodeRings DNS zone."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nr_dns  # noqa: E402
import nr_rundeck  # noqa: E402
from nr_client import is_not_found  # noqa: E402
from nr_rundeck import config, config_list  # noqa: E402


def find_zone(client, zone):
    want = nr_dns.normalize_zone_name(zone)
    for z in client.list_dns_zones():
        if z.get("id") == zone or nr_dns.normalize_zone_name(z.get("name")) == want:
            return z
    raise nr_rundeck.StepFailure(f"NodeRings DNS zone {zone} does not exist")


def find_record(client, zone_id, rel, rtype):
    for rec in client.list_dns_records(zone_id, "" if rel == "@" else rel, rtype):
        if (
            nr_dns.relative_name(rec.get("name"), "") == rel
            and (rec.get("type") or "").upper() == rtype
            and not rec.get("system")
        ):
            return rec
    return None


def apply(client, env=None, out=None):
    out = out or sys.stdout
    zone = find_zone(client, config("zone", "", env))
    rtype = (config("type", "", env) or "").upper()
    if rtype not in nr_dns.RECORD_TYPES:
        raise nr_rundeck.StepFailure(f"type must be one of {', '.join(nr_dns.RECORD_TYPES)}")
    rel = nr_dns.relative_name(config("name", "@", env), zone.get("name"))
    current = find_record(client, zone["id"], rel, rtype)
    label = f"{rel} {rtype} in {zone.get('name')}"

    if config("action", "set", env) == "delete":
        if not current:
            print(f"{label} does not exist; nothing to delete.", file=out)
            return False
        try:
            client.delete_dns_record(zone["id"], rel, rtype)
        except Exception as exc:  # pylint: disable=broad-except
            if not is_not_found(exc):
                raise
        print(f"Deleted {label}.", file=out)
        return True

    values = config_list("values", env)
    error = nr_dns.validate_values(rtype, values)
    if error:
        raise nr_rundeck.StepFailure(f"{label}: {error}")
    ttl = int(config("ttl", "3600", env))
    have = [nr_dns.from_api(rtype, v) for v in (current or {}).get("rdata") or []]
    if current and int(current.get("ttl") or 0) == ttl and nr_dns.same_values(rtype, have, values):
        print(f"{label} already holds {', '.join(values)}.", file=out)
        return False
    client.upsert_dns_record(
        zone["id"], {"name": rel, "type": rtype, "ttl": ttl, "rdata": [nr_dns.to_api(rtype, v) for v in values]}
    )
    print(f"Set {label} to {', '.join(values)} (ttl {ttl}).", file=out)
    return True


def main():
    apply(nr_rundeck.client())


if __name__ == "__main__":
    nr_rundeck.run(main)
