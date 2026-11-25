import io
import json

import pytest

import dns_record
import nodes
import nr_rundeck
import vm_create
import vm_delete
import vm_power

OFFER = {"RD_CONFIG_PLAN": "SC-GC-1C-1G-20", "RD_CONFIG_COUNTRY": "United States", "RD_CONFIG_CITY": "Ashburn"}


def add_key(fake, name="laptop"):
    fake(
        "https://api.noderings.com/v1/ssh-keys",
        "POST",
        json.dumps({"name": name, "publicKey": "ssh-ed25519 AAAA"}).encode(),
        {},
        1,
    )


def create(client, env, **extra):
    out = io.StringIO()
    env.update(OFFER, RD_CONFIG_HOSTNAME="web-1", RD_CONFIG_SSH_KEYS="laptop", **extra)
    return vm_create.create(client, env, out), out.getvalue()


def test_create_orders_and_outputs_job_data(client, env, fake):
    add_key(fake)
    vm, log = create(client, env, RD_CONFIG_TAGS="web, rundeck", RD_CONFIG_DISTRO="debian_13")
    body = fake.created_vm_bodies[-1]
    assert body["hostname"] == "web-1" and body["distro"] == "DISTRO_DEBIAN_13"
    assert body["tags"] == ["rundeck", "web"]
    assert body["sshKeyIds"] == [list(fake.ssh_keys)[0]]
    assert f"RUNDECK:DATA:noderings_vm_id={vm['id']}" in log
    assert "RUNDECK:DATA:noderings_ipv4=192.0.2.50" in log
    assert "Ordering web-1: SC-GC-1C-1G-20 from Cheap Host in Ashburn" in log


def test_create_refuses_or_reuses_an_existing_vm(client, env, fake):
    add_key(fake)
    create(client, env)
    with pytest.raises(nr_rundeck.StepFailure, match="already exists"):
        create(client, env)
    vm, log = create(client, env, RD_CONFIG_IF_EXISTS="reuse")
    assert "nothing ordered" in log and len(fake.created_vm_bodies) == 1


def test_create_needs_an_offer_and_a_login(client, env):
    env.update(RD_CONFIG_HOSTNAME="web-1")
    with pytest.raises(nr_rundeck.StepFailure, match="give plan, country and city"):
        vm_create.create(client, env, io.StringIO())
    env.update(OFFER)
    with pytest.raises(nr_rundeck.StepFailure, match="needs ssh_keys or a root password"):
        vm_create.create(client, env, io.StringIO())


def test_power_and_delete(client, env, fake):
    add_key(fake)
    vm, _ = create(client, env)
    env["RD_CONFIG_ACTION"] = "stop"
    vm_power.power(client, env, io.StringIO())
    assert fake.vms[vm["id"]]["operationStatus"] == "OPERATION_STATUS_STOPPED"
    out = io.StringIO()
    vm_power.power(client, env, out)
    assert "already stopped" in out.getvalue()
    env["RD_CONFIG_ACTION"] = "start"
    vm_power.power(client, env, io.StringIO())
    assert fake.vms[vm["id"]]["operationStatus"] == "OPERATION_STATUS_STARTED"
    assert vm_delete.delete(client, env, io.StringIO()) is True
    assert fake.vms == {}
    assert vm_delete.delete(client, env, io.StringIO()) is False
    env["RD_CONFIG_FAIL_IF_MISSING"] = "true"
    with pytest.raises(nr_rundeck.StepFailure, match="no NodeRings virtual machine"):
        vm_delete.delete(client, env, io.StringIO())


def test_node_source(client, env, fake):
    add_key(fake)
    create(client, env, RD_CONFIG_TAGS="web")
    env.update(RD_CONFIG_HOSTNAME="db-1", RD_CONFIG_TAGS="db")
    vm_create.create(client, env, io.StringIO())
    env["RD_CONFIG_SSH_KEY_STORAGE_PATH"] = "keys/project/noderings/id_ed25519"
    listed = nodes.nodes(client, env)
    assert set(listed) == {"web-1", "db-1"}
    web = listed["web-1"]
    assert web["hostname"] == "192.0.2.50" and web["username"] == "root"
    assert web["ssh-key-storage-path"] == "keys/project/noderings/id_ed25519"
    assert {"web", "noderings", "running", "sc-gc-1c-1g-20"} <= set(web["tags"].split(","))
    assert web["noderings-id"] == fake.vms[web["noderings-id"]]["id"]
    env["RD_CONFIG_TAG_FILTER"] = "web"
    assert set(nodes.nodes(client, env)) == {"web-1"}
    json.dumps(listed)  # what nodes.py prints


def test_dns_record_set_idempotent_and_delete(client, env, fake):
    fake("https://api.noderings.com/v1/dns/zones", "POST", b'{"name":"example.com"}', {}, 1)
    zone_id = list(fake.zones)[0]
    env.update(
        RD_CONFIG_ZONE="example.com",
        RD_CONFIG_NAME="www",
        RD_CONFIG_TYPE="A",
        RD_CONFIG_VALUES="192.0.2.10\n192.0.2.11",
        RD_CONFIG_TTL="300",
    )
    assert dns_record.apply(client, env, io.StringIO()) is True
    assert fake.records[zone_id][("www", "A")] == {"ttl": 300, "rdata": ["192.0.2.10", "192.0.2.11"]}
    out = io.StringIO()
    assert dns_record.apply(client, env, out) is False and "already holds" in out.getvalue()
    env.update(RD_CONFIG_NAME="@", RD_CONFIG_TYPE="TXT", RD_CONFIG_VALUES="v=spf1 -all")
    dns_record.apply(client, env, io.StringIO())
    assert fake.records[zone_id][("@", "TXT")]["rdata"] == ['"v=spf1 -all"']
    env.update(RD_CONFIG_NAME="www", RD_CONFIG_TYPE="A", RD_CONFIG_ACTION="delete")
    assert dns_record.apply(client, env, io.StringIO()) is True
    assert ("www", "A") not in fake.records[zone_id]


def test_dns_record_validation(client, env, fake):
    fake("https://api.noderings.com/v1/dns/zones", "POST", b'{"name":"example.com"}', {}, 1)
    env.update(RD_CONFIG_ZONE="example.com", RD_CONFIG_NAME="www", RD_CONFIG_TYPE="A", RD_CONFIG_VALUES="2001:db8::1")
    with pytest.raises(nr_rundeck.StepFailure, match="not an IPv4 address"):
        dns_record.apply(client, env, io.StringIO())
    env.update(RD_CONFIG_ZONE="nope.example")
    with pytest.raises(nr_rundeck.StepFailure, match="does not exist"):
        dns_record.apply(client, env, io.StringIO())


def test_missing_token_is_a_clean_failure(fake):
    with pytest.raises(nr_rundeck.StepFailure, match="Key Storage"):
        nr_rundeck.client({}, opener=fake)


def test_run_reports_errors_without_traceback(capsys):
    def boom():
        raise nr_rundeck.StepFailure("something went wrong")

    with pytest.raises(SystemExit) as exit_info:
        nr_rundeck.run(boom)
    assert exit_info.value.code == 1
    assert capsys.readouterr().err.strip() == "NodeRings: something went wrong"
