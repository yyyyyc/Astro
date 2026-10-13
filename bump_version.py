"""Bump the app version shown on the main page. Run before every git push.

Usage:
    python bump_version.py          # 1.0.3 -> 1.0.4
    python bump_version.py minor    # 1.0.3 -> 1.1.0
    python bump_version.py major    # 1.0.3 -> 2.0.0
"""
import json
import sys
from datetime import datetime
from pathlib import Path

VERSION_FILE = Path(__file__).with_name("version.json")


def bump(part="patch"):
    data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    major, minor, patch = (int(n) for n in data["version"].split("."))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        raise SystemExit(f"Unknown part '{part}' (use major, minor or patch)")

    data = {
        "version": f"{major}.{minor}.{patch}",
        "datetime": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    VERSION_FILE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    result = bump(sys.argv[1] if len(sys.argv) > 1 else "patch")
    print(f"Version {result['version']} ({result['datetime']})")
