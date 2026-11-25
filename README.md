# NodeRings plugin for Rundeck

[![CI](https://github.com/noderings/rundeck-noderings-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/noderings/rundeck-noderings-plugin/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/noderings/rundeck-noderings-plugin?sort=semver)](https://github.com/noderings/rundeck-noderings-plugin/releases)
[![Rundeck](https://img.shields.io/badge/rundeck-tested%20on%206.3-F73F39.svg)](https://www.rundeck.com)

A [Rundeck](https://www.rundeck.com) plugin for [NodeRings](https://noderings.com). Your
NodeRings virtual machines show up as Rundeck nodes, and job steps order, power and delete
servers and manage DNS records, so runbooks like "build a server, point DNS at it and
deploy" run end to end in one job.

New to it? The step-by-step guide [How to use Rundeck on NodeRings to order a VPS and point DNS at it](https://noderings.com/blog/rundeck-vps) walks through a first run.

It works with Rundeck open source and PagerDuty Process Automation (Rundeck 4 and later).

## What's in it

| Provider | Type | What it does |
| --- | --- | --- |
| **NodeRings** | Node source | Lists the organization's VMs as nodes, with tags and attributes |
| **NodeRings / Create VM** | Workflow step | Orders the cheapest matching offer and waits until it runs; outputs its IP as job data |
| **NodeRings / Power** | Workflow step | Starts, stops or restarts a VM |
| **NodeRings / Delete VM** | Workflow step | Deletes a VM |
| **NodeRings / DNS record** | Workflow step | Sets or deletes the records of one name and type in a zone |

## Requirements

* Rundeck 4 or later, or PagerDuty Process Automation
* **Python 3** on the Rundeck server, as `python3`. The plugin uses the Python standard
  library only, so nothing needs `pip install`. The official Rundeck Docker image has no
  Python; see [Docker](#docker).
* A NodeRings service account token. Create one in the NodeRings console under
  **Organization → Access Control → Service accounts**.
* For Create VM: a payment method or credit on the organization. Ordering a server is
  billed; hourly (usage) plans stop billing when the VM is deleted.

## Installation

Download `rundeck-noderings-plugin-<version>.zip` from the
[releases](https://github.com/noderings/rundeck-noderings-plugin/releases), then either:

* in Rundeck: **System menu (gear) → Plugins → Upload Plugin**, or
* copy the zip into `$RDECK_BASE/libext/` on the Rundeck server.

## Setup

1. **Store the token** for the node source in the project's Key Storage:
   **Project Settings → Key Storage → Add or Upload a Key**, type **Password**, path
   `keys/project/<project>/noderings/token`, and paste the NodeRings token.
2. **Let the node source read it.** Rundeck runs node sources as the project itself
   (`urn:project:<project>`), not as a user, so it needs read access to that key. Add this
   policy in **System → Access Control → Create ACL Policy** (replace `myproject` twice in each
   half):

   ```yaml
   description: Let the myproject node sources read the project's keys
   context:
     application: rundeck
   for:
     storage:
       - match:
           path: 'keys/project/myproject(/.*)?'
         allow: [read]
   by:
     urn: project:myproject
   ---
   description: The same read, checked in the project context
   context:
     project: 'myproject'
   for:
     storage:
       - match:
           path: 'keys/project/myproject(/.*)?'
         allow: [read]
   by:
     urn: project:myproject
   ```

   Without it, the node source shows *Unable to load configuration key 'api_token' value from
   storage path* under **Project Settings → Edit Nodes**.
3. **Optional: store an SSH key** for logging in to the VMs (**Private Key**, for example
   `keys/noderings/id_rsa`). Add its public half to NodeRings so new VMs get it. Rundeck's SSH
   executor reads it as the user running the job.
4. **Add the node source.** **Project Settings → Edit Nodes → Add a new Node Source →
   NodeRings**. Select the token, and optionally the SSH key, an SSH user (default `root`),
   tags to filter on, and whether to list only running VMs.

The workflow steps run as the user who runs the job, so their **API token** setting can point
at any key that user may read, for example `keys/noderings/token`; no extra policy is needed.

Each VM becomes a node named after its hostname:

| Node field | From NodeRings |
| --- | --- |
| `hostname` | IPv4 address (IPv6 when there is none) |
| `username` | The SSH user setting (default `root`) |
| `tags` | The VM's tags, plus `noderings`, its power state, city and plan code |
| `osVersion` | Distro, such as `ubuntu_24_04` |
| `ssh-key-storage-path` | The SSH key setting, so Rundeck's SSH executor logs in with it |
| `noderings-*` attributes | ID, distro, power state, plan, provider, country, city, IPv4, IPv6, firewall ruleset |

Run commands across servers with node filters such as `tags: web` or
`noderings-city: Ashburn`.

## Workflow steps

Every step has the same **API token** setting (a Key Storage path) plus its own options.
The steps run on the Rundeck server itself (they are not node steps), so the project needs
the server's own node, which Rundeck's built-in **Local** node source provides; new projects
have it by default.

**Create VM**: hostname, plan code, country and city (or an exact plan ID and region ID),
operating system, NodeRings SSH keys (names) or a root password from Key Storage, tags,
firewall ruleset, billing type, and whether to fail or reuse a VM that already exists. The
order carries an idempotency key, so a lost response never orders a second server.

The step prints `RUNDECK:DATA:noderings_ipv4=...`, `noderings_ipv6` and `noderings_vm_id`.
Add the **Key Value Data** log filter to the job (default pattern), and later steps can use
`${data.noderings_ipv4}`:

```yaml
- name: build web server
  sequence:
    commands:
      - type: noderings-vm-create
        nodeStep: false
        configuration:
          api_token: keys/noderings/token
          hostname: web-1
          plan: SC-GC-1C-1G-20
          country: United States
          city: Ashburn
          distro: ubuntu_24_04
          ssh_keys: deploy
          tags: web
      - type: noderings-dns-record
        nodeStep: false
        configuration:
          api_token: keys/noderings/token
          zone: example.com
          name: www
          type: A
          values: ${data.noderings_ipv4}
          ttl: "300"
    pluginConfig:
      LogFilter:
        - type: key-value-data
          config:
            logData: "true"
            regex: ^RUNDECK:DATA:\s*([^\s]+?)\s*=\s*(.+)$
```

**Power**: hostname or ID, and `start`, `stop` or `restart`. Waits until the VM reaches the
state; asking to start a running VM changes nothing.

**Delete VM**: hostname or ID. A missing VM is fine unless **Fail if missing** is on. An
hourly VM stops billing; a monthly subscription is cancelled without a refund.

**DNS record**: zone, name (`www`, or `@` for the apex), type, values (one per line or comma
separated), TTL, and `set` or `delete`. `set` replaces the values of that name and type and
changes nothing when they already match. Write hostnames with a trailing dot; TXT values are
plain text.

A failing step stops the job with the API's message, for example
`NodeRings: No offer for plan code ... in Nowhere, United States`.

## Docker

The official image has no Python, so add it:

```dockerfile
FROM rundeck/rundeck:6.3.0
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
USER rundeck
COPY rundeck-noderings-plugin-0.1.0.zip /home/rundeck/libext/
```

[`docker/Dockerfile`](docker/Dockerfile) is the same file, used by the tests.

## Development

```shell
pip install pytest pyyaml ruff
pytest                          # unit tests against an in-memory NodeRings API
ruff check . && ruff format --check .
python3 build.py                # writes build/rundeck-noderings-plugin-<version>.zip
```

[`tests/e2e/rundeck_e2e.py`](tests/e2e/rundeck_e2e.py) runs the whole plugin in a real
Rundeck against the real API: it creates a project with the node source, orders a VM and
points DNS at it, runs a command on it over SSH, stops and starts it, deletes it, and removes
everything it made. It orders one billed VM:

```shell
python3 build.py && docker build -f docker/Dockerfile -t rundeck-noderings .
docker run -d -p 127.0.0.1:4440:4440 -e RUNDECK_TOKENS_FILE=... rundeck-noderings
RUNDECK_TOKEN=... NODERINGS_TOKEN=... python3 tests/e2e/rundeck_e2e.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Copyright NodeRings. Licensed under the [Apache License, Version 2.0](LICENSE).
