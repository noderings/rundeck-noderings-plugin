"""
What every NodeRings plugin script shares: reading the plugin configuration that
Rundeck passes as RD_CONFIG_* environment variables, building the API client,
reporting results and failing cleanly.
"""

import os
import sys

from nr_client import NodeRingsClient, NodeRingsError, TimeoutError_
from nr_compute import NodeRingsUsageError
from nr_version import __version__


class StepFailure(Exception):
    """A failure to report to the job log without a traceback."""


def config(name, default=None, env=None):
    """A plugin setting: RD_CONFIG_<NAME>, or None/default when it is empty."""
    env = os.environ if env is None else env
    value = env.get(f"RD_CONFIG_{name.upper()}")
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def config_list(name, env=None):
    """A setting holding a list, separated by commas or new lines."""
    value = config(name, "", env)
    return [v.strip() for v in value.replace("\n", ",").split(",") if v.strip()]


def config_bool(name, default=False, env=None):
    value = config(name, None, env)
    return default if value is None else value.lower() in ("true", "yes", "1")


def client(env=None, opener=None, sleep=None):
    """The API client. The token comes from Rundeck Key Storage (or NODERINGS_TOKEN)."""
    env = os.environ if env is None else env
    token = config("api_token", None, env) or env.get("NODERINGS_TOKEN")
    kwargs = {}
    if opener is not None:
        kwargs["opener"] = opener
    if sleep is not None:
        kwargs["sleep"] = sleep
    try:
        return NodeRingsClient(
            token=token,
            api_url=config("api_url", None, env),
            organization_id=config("organization_id", None, env),
            user_agent=f"rundeck-noderings-plugin/{__version__}",
            **kwargs,
        )
    except ValueError as exc:
        raise StepFailure(str(exc)) from exc


def data(name, value, out=None):
    """
    A value for later steps. With the job's "Key Value Data" log filter on its
    default pattern, it becomes ${data.<name>}.
    """
    out = out or sys.stdout
    if value not in (None, ""):
        print(f"RUNDECK:DATA:{name}={value}", file=out)


def run(main):
    """Run a script's main(); API and usage errors exit 1 with a readable message."""
    try:
        main()
    except (StepFailure, NodeRingsUsageError, NodeRingsError, TimeoutError_) as exc:
        print(f"NodeRings: {exc}", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"NodeRings: could not reach the API: {exc}", file=sys.stderr)
        sys.exit(1)
