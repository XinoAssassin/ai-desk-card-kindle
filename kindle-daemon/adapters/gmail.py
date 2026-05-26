"""Gmail unread-count adapter via Gmail API (OAuth2 desktop flow).

Setup (one-time):
  1. Save Google Cloud OAuth client_secret.json at:
       ~/.config/kindle-desk-card/client_secret.json
  2. First run triggers browser-based OAuth — click Allow.
  3. Token cached at:
       ~/.config/kindle-desk-card/gmail_token.json   (0600)

Output shape (matches paint_inbox):
  {"total": <int>,
   "sources": [
     {"name": "Inbox",     "count": <int>},
     {"name": "Important", "count": <int>},
     {"name": "Starred",   "count": <int>},
   ]}
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Google APIs are unreachable from some corp networks without an HTTP proxy.
# Exchange / Lark adapters point at internal hosts that MUST bypass the proxy,
# so we scope the proxy strictly to this adapter's network calls via the
# context manager below.
DEFAULT_PROXY = "http://127.0.0.1:7890"


@contextlib.contextmanager
def _proxy_env():
    proxy = os.environ.get("KINDLE_GMAIL_PROXY", DEFAULT_PROXY)
    if not proxy:
        yield
        return
    saved = {k: os.environ.get(k) for k in ("HTTPS_PROXY", "HTTP_PROXY")}
    os.environ["HTTPS_PROXY"] = proxy
    os.environ["HTTP_PROXY"] = proxy
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


CONFIG_DIR = Path.home() / ".config" / "kindle-desk-card"
CLIENT_SECRET = CONFIG_DIR / "client_secret.json"
TOKEN_PATH = CONFIG_DIR / "gmail_token.json"

# Read-only is enough to count unread + read labels
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Which labels to surface as "sources" rows. Gmail Inbox total goes first.
SOURCE_LABELS: list[tuple[str, str]] = [
    ("INBOX",     "Inbox"),
    ("IMPORTANT", "Important"),
    ("STARRED",   "Starred"),
]


def _get_credentials() -> Credentials:
    creds: Credentials | None = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        if not CLIENT_SECRET.exists():
            raise RuntimeError(f"missing OAuth client secret: {CLIENT_SECRET}")
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        # Loopback flow — opens browser, listens on a random local port for the callback.
        creds = flow.run_local_server(port=0, open_browser=True)

    # Persist with restrictive perms
    TOKEN_PATH.write_text(creds.to_json())
    os.chmod(TOKEN_PATH, 0o600)
    return creds


def fetch() -> dict:
    with _proxy_env():
        creds = _get_credentials()
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        sources: list[dict] = []
        inbox_unread = 0
        for label_id, display in SOURCE_LABELS:
            try:
                info = service.users().labels().get(userId="me", id=label_id).execute()
            except Exception:
                continue
            n = int(info.get("messagesUnread", 0))
            if label_id == "INBOX":
                inbox_unread = n
            if n > 0:
                sources.append({"name": display, "count": n})

    # If nothing unread anywhere, still surface the Inbox row at zero so the
    # widget shows the "封 0" state instead of "暂无数据"
    if not sources:
        sources = [{"name": "Inbox", "count": 0}]

    return {
        "total": inbox_unread,
        "sources": sources[:4],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
