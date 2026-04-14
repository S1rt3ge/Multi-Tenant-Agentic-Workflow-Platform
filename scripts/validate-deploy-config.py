import os
import sys


REQUIRED_SECRETS = [
    "DEPLOY_HOST",
    "DEPLOY_USER",
    "DEPLOY_PATH",
    "DB_PASSWORD",
    "JWT_SECRET",
]

OPTIONAL_SECRETS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
]

REQUIRED_VARS = [
    "CORS_ORIGINS",
]

OPTIONAL_VARS = [
    "LOG_LEVEL",
    "LOG_FORMAT",
    "VITE_API_URL",
]


def main() -> int:
    missing = []

    for key in REQUIRED_SECRETS:
        value = os.getenv(key, "").strip()
        if not value:
            missing.append(f"secret:{key}")

    for key in REQUIRED_VARS:
        value = os.getenv(key, "").strip()
        if not value:
            missing.append(f"var:{key}")

    if missing:
        print("Missing deployment configuration:", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Required deployment configuration is present.")

    for key in OPTIONAL_SECRETS + OPTIONAL_VARS:
        if not os.getenv(key, "").strip():
            print(f"Optional deployment configuration not set: {key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
