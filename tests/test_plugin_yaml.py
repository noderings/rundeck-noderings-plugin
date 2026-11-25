import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = yaml.safe_load((ROOT / "plugin.yaml").read_text())


def test_every_script_exists_and_runs_with_python3():
    for p in PLUGIN["providers"]:
        assert (ROOT / "contents" / p["script-file"]).exists(), p["script-file"]
        assert p["script-interpreter"].startswith("python3")


def test_every_provider_reads_the_token_from_key_storage():
    for p in PLUGIN["providers"]:
        token = next(c for c in p["config"] if c["name"] == "api_token")
        assert token["renderingOptions"]["valueConversion"] == "STORAGE_PATH_AUTOMATIC_READ"


def test_config_names_match_what_the_scripts_read():
    for p in PLUGIN["providers"]:
        source = (ROOT / "contents" / p["script-file"]).read_text() + (ROOT / "contents" / "nr_rundeck.py").read_text()
        read = set(re.findall(r'config(?:_list|_bool)?\("([a-z_]+)"', source))
        names = {c["name"] for c in p["config"]}
        assert read <= names | {"username", "ssh_key_storage_path", "tag_filter", "running_only"}, (p["name"], read - names)
