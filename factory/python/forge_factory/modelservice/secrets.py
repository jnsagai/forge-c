"""Private secret resolver for the model channel (feature 017, FR-018, FR-024).

Recipes and configuration name secrets; this module turns a name into a value, read from one private file
(`name=value` lines, `#` comments) whose path is in FORGE_MODEL_SERVICE_SECRETS. The file must be readable by its
owner only. No secret value ever appears in a repr, a log line or an exception message.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

ENV = "FORGE_MODEL_SERVICE_SECRETS"


class SecretError(RuntimeError):
    """Machine reason in the message, never a secret value."""


class Secret:
    __slots__ = ("name", "_value")

    def __init__(self, name: str, value: str):
        self.name, self._value = name, value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Secret(name={self.name!r}, value=***)"

    __str__ = __repr__


class SecretFile:
    def __init__(self, path: str | Path):
        p = Path(path)
        try:
            st = p.stat()
        except FileNotFoundError:
            raise SecretError(f"SECRETS_FILE_MISSING:{p}") from None
        if st.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise SecretError(f"SECRETS_FILE_NOT_PRIVATE:{p}:{oct(stat.S_IMODE(st.st_mode))}")
        if st.st_uid != os.getuid():
            raise SecretError(f"SECRETS_FILE_NOT_OWNED:{p}")
        self.path, self._values = p, {}
        for n, line in enumerate(p.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise SecretError(f"SECRETS_FILE_MALFORMED:{n}")
            name, value = (x.strip() for x in line.split("=", 1))
            if not name or not value:
                raise SecretError(f"SECRETS_FILE_MALFORMED:{n}")
            self._values[name] = value

    def get(self, name: str) -> Secret:
        if name not in self._values:
            raise SecretError(f"SECRET_NOT_FOUND:{name}")
        return Secret(name, self._values[name])

    def names(self) -> list[str]:
        return sorted(self._values)


def resolve(name: str, path: str | Path | None = None) -> Secret:
    path = path or os.environ.get(ENV)
    if not path:
        raise SecretError(f"SECRETS_FILE_UNSET:{ENV}")
    return SecretFile(path).get(name)
