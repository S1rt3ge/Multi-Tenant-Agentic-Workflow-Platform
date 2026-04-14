import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_VERSION_FILE = ROOT / "backend" / "app" / "core" / "version.py"
FRONTEND_PACKAGE_FILE = ROOT / "frontend" / "package.json"
CLI_PACKAGE_FILE = ROOT / "cli" / "package.json"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"


def read_backend_version() -> str:
    match = re.search(
        r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',
        BACKEND_VERSION_FILE.read_text(encoding="utf-8"),
    )
    if not match:
        raise ValueError("Could not parse APP_VERSION from backend/app/core/version.py")
    return match.group(1)


def read_frontend_version() -> str:
    data = json.loads(FRONTEND_PACKAGE_FILE.read_text(encoding="utf-8"))
    return data["version"]


def read_cli_version() -> str:
    data = json.loads(CLI_PACKAGE_FILE.read_text(encoding="utf-8"))
    return data["version"]


def changelog_contains(version: str) -> bool:
    heading = f"## [{version}]"
    return heading in CHANGELOG_FILE.read_text(encoding="utf-8")


def main() -> int:
    backend_version = read_backend_version()
    frontend_version = read_frontend_version()
    cli_version = read_cli_version()

    if len({backend_version, frontend_version, cli_version}) != 1:
        print(
            f"Version mismatch: backend={backend_version}, frontend={frontend_version}, cli={cli_version}",
            file=sys.stderr,
        )
        return 1

    tag = sys.argv[1] if len(sys.argv) > 1 else None
    if tag:
        normalized = tag[1:] if tag.startswith("v") else tag
        if normalized != backend_version:
            print(
                f"Tag version mismatch: tag={tag}, expected=v{backend_version}",
                file=sys.stderr,
            )
            return 1

    if not changelog_contains(backend_version):
        print(
            f"CHANGELOG.md is missing a section for version {backend_version}",
            file=sys.stderr,
        )
        return 1

    print(
        f"Release metadata OK: version={backend_version}, tag={tag or 'not provided'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
