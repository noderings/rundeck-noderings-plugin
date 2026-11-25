"""
Builds the plugin zip Rundeck installs:

    build/rundeck-noderings-plugin-<version>.zip
      rundeck-noderings-plugin-<version>/plugin.yaml
      rundeck-noderings-plugin-<version>/contents/*.py

The version comes from the first argument, the git tag (v1.2.3 or 1.2.3), or
contents/nr_version.py.
"""

import datetime
import pathlib
import re
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
NAME = "rundeck-noderings-plugin"


def version():
    if len(sys.argv) > 1:
        return sys.argv[1].removeprefix("v")
    try:
        tag = subprocess.run(["git", "describe", "--tags", "--exact-match"], cwd=ROOT, capture_output=True, text=True, check=True)
        return tag.stdout.strip().removeprefix("v")
    except (subprocess.CalledProcessError, FileNotFoundError):
        text = (ROOT / "contents" / "nr_version.py").read_text()
        return re.search(r'__version__ = "([^"]+)"', text).group(1)


def main():
    ver = version()
    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    top = f"{NAME}-{ver}"
    out = ROOT / "build" / f"{top}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = (ROOT / "plugin.yaml").read_text().replace("@version@", ver).replace("@date@", date)
        zf.writestr(f"{top}/plugin.yaml", manifest)
        for path in sorted((ROOT / "contents").glob("*.py")):
            text = path.read_text()
            if path.name == "nr_version.py":
                text = f'"""The plugin version."""\n\n__version__ = "{ver}"\n'
            zf.writestr(f"{top}/contents/{path.name}", text)
        icon = ROOT / "resources" / "icon.png"
        if icon.exists():
            zf.write(icon, f"{top}/resources/icon.png")
    print(out)


if __name__ == "__main__":
    main()
