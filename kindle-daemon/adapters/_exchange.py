"""Shared Exchange (EWS) account loader for calendar + inbox adapters.

Reads credentials from ~/.config/kindle-desk-card/exchange.env (mode 0600):
    EXCHANGE_EMAIL=you@example.com
    EXCHANGE_USERNAME=you@example.com
    EXCHANGE_PASSWORD=...
    EXCHANGE_SERVER=mail.example.com

Account object is cached at module level so both calendar and inbox adapters
share one EWS session per process — saves a TLS handshake per refresh tick.
"""
from __future__ import annotations

import logging
import warnings
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message="Cannot convert value .* on field .* to type 'EWSTimeZone'.*",
)

from exchangelib import (  # noqa: E402
    Account,
    Configuration,
    Credentials,
    DELEGATE,
    NTLM,
)

logging.getLogger("exchangelib").setLevel(logging.WARNING)


ENV_PATH = Path.home() / ".config" / "kindle-desk-card" / "exchange.env"

_account_cache: Account | None = None


def _load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        raise RuntimeError(f"missing credentials file: {path}")
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    for required in ("EXCHANGE_EMAIL", "EXCHANGE_USERNAME", "EXCHANGE_PASSWORD", "EXCHANGE_SERVER"):
        if required not in out or not out[required]:
            raise RuntimeError(f"{required} not set in {path}")
    return out


def get_account() -> Account:
    global _account_cache
    if _account_cache is not None:
        return _account_cache
    env = _load_env(ENV_PATH)
    creds = Credentials(username=env["EXCHANGE_USERNAME"], password=env["EXCHANGE_PASSWORD"])
    config = Configuration(server=env["EXCHANGE_SERVER"], credentials=creds, auth_type=NTLM)
    _account_cache = Account(
        primary_smtp_address=env["EXCHANGE_EMAIL"],
        config=config,
        autodiscover=False,
        access_type=DELEGATE,
    )
    return _account_cache
