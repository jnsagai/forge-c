"""Store/remove a provider key in an isolated Fabro server vault (`/api/v1/secrets`, verified in the 0.362 OpenAPI).

Used only by the user-authorized cloud benchmark stack. The key is read from a local env file and sent to the
loopback server; it is never printed, logged or written to Forge-C files.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx


def _token(storage: Path) -> str:
    return next(line.split("=", 1)[1].strip() for line in (storage / "server.env").read_text().splitlines()
                if line.startswith("FABRO_DEV_TOKEN="))


def _req(url: str, token: str, method: str, body: dict | None = None) -> int:
    r = httpx.request(method, url + "/secrets", json=body, timeout=30,
                      headers={"Authorization": "Bearer " + token})
    r.raise_for_status()
    return r.status_code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["store", "purge"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--storage", type=Path, required=True)
    ap.add_argument("--name", default="DEEPSEEK_API_KEY")
    ap.add_argument("--env-file", type=Path, default=Path(os.path.expanduser("~/.config/sesn/deepseek.env")))
    a = ap.parse_args(argv)
    if not a.url.startswith("http://127.0.0.1:"):
        raise SystemExit("vault helper only talks to a loopback Fabro server")
    tok = _token(a.storage)
    if a.action == "purge":
        print(json.dumps({"purged": a.name, "status": _req(a.url, tok, "DELETE", {"name": a.name})}))
        return 0
    value = next(line.split("=", 1)[1].strip() for line in a.env_file.read_text().splitlines()
                 if line.removeprefix("export ").startswith(a.name + "="))
    status = _req(a.url, tok, "POST", {"name": a.name, "value": value, "type": "token",
                                       "description": "Forge-C cloud benchmark (user-authorized)"})
    print(json.dumps({"stored": a.name, "status": status}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
