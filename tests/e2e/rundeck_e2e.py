"""
End-to-end test: a real Rundeck with the plugin installed, against the real
NodeRings API. It orders one billed VM and removes everything it creates.

    RUNDECK_URL=http://127.0.0.1:4440 RUNDECK_TOKEN=... NODERINGS_TOKEN=... python3 tests/e2e/rundeck_e2e.py

Steps:
 1. Key Storage: the NodeRings token (password) and a new SSH private key.
 2. NodeRings: the matching public key, and a DNS zone for the test.
 3. A project whose node source is the plugin, filtered to this run's tag.
 4. Job "create": NodeRings / Create VM, then NodeRings / DNS record pointing at
    ${data.noderings_ipv4} from the first step.
 5. The node source lists the VM; job "run" executes a command on it over SSH.
 6. Job "power": stop, then start. Job "cleanup": delete the VM and the record.
 7. Removes the zone, the key and the project, and checks nothing is left.
"""

import contextlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

RD = os.environ.get("RUNDECK_URL", "http://127.0.0.1:4440").rstrip("/")
RD_TOKEN = os.environ["RUNDECK_TOKEN"]
NR_TOKEN = os.environ["NODERINGS_TOKEN"]
NR = os.environ.get("NODERINGS_API_URL", "https://api.noderings.com").rstrip("/")
API = 60
RUN = f"rd-e2e-{uuid.uuid4().hex[:6]}"
PROJECT = RUN
ZONE = f"{RUN}.{os.environ.get('NODERINGS_TEST_DOMAIN', 'example.com')}"
OFFER = {
    "plan": os.environ.get("NODERINGS_TEST_PLAN_CODE", "SC-GC-1C-1G-20"),
    "country": os.environ.get("NODERINGS_TEST_COUNTRY", "United States"),
    "city": os.environ.get("NODERINGS_TEST_CITY", "Ashburn"),
}


def http(method, url, body=None, headers=None, ctype="application/json"):
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else (body.encode() if isinstance(body, str) else json.dumps(body).encode())
    req = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", **(headers or {})})
    if data is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {url}: HTTP {exc.code}: {exc.read()[:400]!r}") from exc
    return json.loads(raw) if raw.strip().startswith((b"{", b"[")) else raw


def rd(method, path, body=None, ctype="application/json"):
    return http(method, f"{RD}/api/{API}{path}", body, {"X-Rundeck-Auth-Token": RD_TOKEN}, ctype)


def nr(method, path, body=None):
    return http(method, f"{NR}{path}", body, {"Authorization": f"Bearer {NR_TOKEN}", "User-Agent": "rundeck-noderings-e2e"})


def step(msg):
    print(f"\n== {msg}", flush=True)


def run_job(job_id, timeout=1800):
    ex = rd("POST", f"/job/{job_id}/run", {})
    eid = ex["id"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = rd("GET", f"/execution/{eid}")
        if state["status"] not in ("running", "scheduled", "queued"):
            break
        time.sleep(5)
    out = rd("GET", f"/execution/{eid}/output")
    lines = [e.get("log", "") for e in out.get("entries", [])]
    print("\n".join(f"   | {line}" for line in lines))
    if state["status"] != "succeeded":
        raise RuntimeError(f"job execution {eid} ended {state['status']}")
    return lines


def job(name, commands, extra=None):
    d = {
        "name": name,
        "group": "noderings",
        "loglevel": "INFO",
        "sequence": {
            "keepgoing": False,
            "strategy": "node-first",
            "commands": commands,
            "pluginConfig": {
                "LogFilter": [
                    {"type": "key-value-data", "config": {"logData": "true", "regex": r"^RUNDECK:DATA:\s*([^\s]+?)\s*=\s*(.+)$"}}
                ]
            },
        },
    }
    d.update(extra or {})
    return d


def node_source_acl(project):
    """The policy that lets a project's node sources read the project's keys (see README)."""
    rule = f"""for:
  storage:
    - match:
        path: 'keys/project/{project}(/.*)?'
      allow: [read]
by:
  urn: project:{project}
"""
    return (
        f"description: Let the {project} project's node sources read its keys\ncontext:\n  application: rundeck\n{rule}"
        f"---\ndescription: The same read, checked in the project context\ncontext:\n  project: '{project}'\n{rule}"
    )


def nr_step(kind, **config):
    return {"type": kind, "nodeStep": False, "configuration": {"api_token": "keys/noderings/token", **config}}


def main():  # noqa: PLR0915
    created = {"zone": None, "key": None, "project": False, "acl": False}
    tmp = tempfile.mkdtemp()
    try:
        step("Key Storage: NodeRings token and an SSH key")
        rd("POST", "/storage/keys/noderings/token", NR_TOKEN, "application/x-rundeck-data-password")
        # The node source reads keys as the project (urn:project:<name>), so its token lives under
        # keys/project/<name>/ with an ACL that lets the project read it, as the README describes.
        rd("POST", f"/storage/keys/project/{PROJECT}/noderings/token", NR_TOKEN, "application/x-rundeck-data-password")
        rd("POST", f"/system/acl/{PROJECT}-nodes.aclpolicy", node_source_acl(PROJECT), "application/yaml")
        created["acl"] = True
        subprocess.run(["ssh-keygen", "-q", "-t", "rsa", "-b", "3072", "-m", "PEM", "-N", "", "-f", f"{tmp}/k"], check=True)
        with open(f"{tmp}/k", "rb") as fh:
            rd("POST", "/storage/keys/noderings/id_rsa", fh.read(), "application/octet-stream")

        step("NodeRings: SSH key and DNS zone for this run")
        with open(f"{tmp}/k.pub") as fh:
            key = nr("POST", "/v1/ssh-keys", {"name": RUN, "publicKey": fh.read().strip()})["sshKey"]
        created["key"] = key["id"]
        zone = nr("POST", "/v1/dns/zones", {"name": ZONE})["zone"]
        created["zone"] = zone["id"]

        step(f"Project {PROJECT} with the NodeRings node source")
        rd(
            "POST",
            "/projects",
            {
                "name": PROJECT,
                "config": {
                    # The Rundeck server's own node, where workflow steps run.
                    "resources.source.1.type": "local",
                    "resources.source.2.type": "noderings-nodes",
                    "resources.source.2.config.api_token": f"keys/project/{PROJECT}/noderings/token",
                    "resources.source.2.config.ssh_key_storage_path": "keys/noderings/id_rsa",
                    "resources.source.2.config.tag_filter": RUN,
                    "project.ssh-authentication": "privateKey",
                    "project.ssh-keypath": "",
                },
            },
        )
        created["project"] = True

        jobs = [
            job(
                "create",
                [
                    nr_step("noderings-vm-create", hostname=f"{RUN}-vm", ssh_keys=RUN, tags=RUN, distro="ubuntu_24_04", **OFFER),
                    nr_step("noderings-dns-record", zone=ZONE, name="web", type="A", values="${data.noderings_ipv4}", ttl="300"),
                ],
            ),
            job(
                "run",
                [{"exec": "hostname && . /etc/os-release && echo $PRETTY_NAME"}],
                {"nodefilters": {"filter": f"tags: {RUN}"}, "nodesSelectedByDefault": True},
            ),
            job("power", [nr_step("noderings-vm-power", hostname=f"{RUN}-vm", action=a) for a in ("stop", "start")]),
            job(
                "cleanup",
                [
                    nr_step("noderings-vm-delete", hostname=f"{RUN}-vm"),
                    nr_step("noderings-dns-record", zone=ZONE, name="web", type="A", action="delete"),
                ],
            ),
        ]
        imported = rd("POST", f"/project/{PROJECT}/jobs/import?format=json&dupeOption=update", jobs)
        ids = {j["name"]: j["id"] for j in imported["succeeded"]}
        if imported.get("failed"):
            raise RuntimeError(f"job import failed: {imported['failed']}")

        step("Job: create the VM and point DNS at it")
        t0 = time.time()
        run_job(ids["create"])
        print(f"   create job took {time.time() - t0:.0f} s")
        vm = next(
            v for v in nr("GET", "/v1/virtual-machines?page=0&pageSize=-1")["virtualMachines"] if v["hostname"] == f"{RUN}-vm"
        )
        recs = nr("GET", f"/v1/dns/zones/{zone['id']}/records?page=0&pageSize=100")["records"]
        web = next(r for r in recs if r["name"].rstrip(".") == "web" and r["type"] == "A")
        assert web["rdata"] == [vm["ipv4"]], (web, vm["ipv4"])
        print(f"   VM {vm['id']} at {vm['ipv4']}; web A -> {web['rdata']}")

        step("Node source lists the VM")
        # Rundeck caches the node list and ACL policies for about 30 s.
        for _ in range(24):
            nodes = rd("GET", f"/project/{PROJECT}/resources")
            if f"{RUN}-vm" in nodes:
                break
            time.sleep(10)
        else:
            sources = rd("GET", f"/project/{PROJECT}/sources")
            raise AssertionError(f"node source never listed the VM: {list(nodes)}; sources: {sources}")
        node = nodes[f"{RUN}-vm"]
        print(f"   {RUN}-vm: hostname={node['hostname']} tags={node['tags']} ssh-key={node.get('ssh-key-storage-path')}")
        assert node["hostname"] == vm["ipv4"]

        step("Job: run a command on the VM over SSH")
        for attempt in range(12):
            try:
                lines = run_job(ids["run"], timeout=300)
                break
            except RuntimeError:
                if attempt == 11:
                    raise
                print("   SSH not ready yet; retrying in 15 s")
                time.sleep(15)
        assert any(line.strip() == f"{RUN}-vm" for line in lines), lines

        step("Job: stop and start")
        run_job(ids["power"])

        step("Job: delete the VM and the record")
        run_job(ids["cleanup"])
        left = [
            v for v in nr("GET", "/v1/virtual-machines?page=0&pageSize=-1")["virtualMachines"] if v["hostname"] == f"{RUN}-vm"
        ]
        assert not left, left
        print("\nEND TO END PASSED")
    finally:
        step("Cleanup")
        for v in nr("GET", "/v1/virtual-machines?page=0&pageSize=-1")["virtualMachines"]:
            if v["hostname"] == f"{RUN}-vm":
                try:
                    nr("DELETE", f"/v1/virtual-machines/{v['id']}")
                    print(f"   deleted leftover VM {v['id']}")
                except RuntimeError as exc:
                    print(f"   VM: {exc}")
        if created["zone"]:
            try:
                nr("DELETE", f"/v1/dns/zones/{created['zone']}?force=true")
            except RuntimeError as exc:
                print(f"   zone: {exc}")
        if created["key"]:
            try:
                nr("DELETE", f"/v1/ssh-keys/{created['key']}")
            except RuntimeError as exc:
                print(f"   key: {exc}")
        for path in (
            "/storage/keys/noderings/token",
            "/storage/keys/noderings/id_rsa",
            f"/storage/keys/project/{PROJECT}/noderings/token",
        ):
            with contextlib.suppress(RuntimeError):
                rd("DELETE", path)
        if created["acl"]:
            try:
                rd("DELETE", f"/system/acl/{PROJECT}-nodes.aclpolicy")
            except RuntimeError as exc:
                print(f"   acl: {exc}")
        if created["project"]:
            try:
                rd("DELETE", f"/project/{PROJECT}")
            except RuntimeError as exc:
                print(f"   project: {exc}")
        vms = [
            v["hostname"] for v in nr("GET", "/v1/virtual-machines?page=0&pageSize=-1")["virtualMachines"] if RUN in v["hostname"]
        ]
        print(f"   VMs left after cleanup: {vms or 'none'}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
