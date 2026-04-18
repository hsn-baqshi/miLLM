"""
Shared Microsoft Graph + MSAL (public client, device flow) for CLI and MCP.

Environment (typical):
  AZURE_TENANT_ID, AZURE_CLIENT_ID — required
  AZURE_LOGIN_HOST — optional (default login.microsoftonline.com)
  GRAPH_API_ROOT — optional (default https://graph.microsoft.com/v1.0)
  GRAPH_SCOPES — optional space-separated; defaults differ by entrypoint
  MSAL_TOKEN_CACHE_PATH — optional path to token cache file
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import msal

DEFAULT_GRAPH_API_ROOT = "https://graph.microsoft.com/v1.0"
DEFAULT_LOGIN_HOST = "login.microsoftonline.com"
DEFAULT_SCOPES_MAIL_READ = ["Mail.Read", "User.Read"]
DEFAULT_SCOPES_MAIL_SEND = ["Mail.Read", "Mail.Send", "User.Read"]

_DEFAULT_CACHE = Path(__file__).resolve().parent / "token_cache.bin"


class GraphSessionError(Exception):
    """Configuration, auth, or Graph HTTP failure."""


def token_cache_path() -> Path:
    raw = os.environ.get("MSAL_TOKEN_CACHE_PATH", "").strip()
    if raw:
        return Path(raw)
    return _DEFAULT_CACHE


def graph_api_root() -> str:
    return (os.environ.get("GRAPH_API_ROOT") or DEFAULT_GRAPH_API_ROOT).strip().rstrip("/")


def azure_authority_url(tenant: str) -> str:
    host = (os.environ.get("AZURE_LOGIN_HOST") or DEFAULT_LOGIN_HOST).strip().rstrip("/")
    return f"https://{host}/{tenant}"


def _graph_response_diagnostics(r: httpx.Response) -> str:
    keys = (
        "www-authenticate",
        "x-ms-ags-diagnostic",
        "request-id",
        "client-request-id",
    )
    picked = {k: r.headers.get(k) for k in keys if r.headers.get(k)}
    return json.dumps(picked, indent=2) if picked else "(no diagnostic headers)"


def _load_cache(path: Path) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if path.exists():
        try:
            cache.deserialize(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return cache


def _save_cache(path: Path, cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(cache.serialize(), encoding="utf-8")


def try_acquire_token_silent(scopes: list[str]) -> str | None:
    """Return access token from cache only; no device flow."""
    tenant = os.environ.get("AZURE_TENANT_ID", "").strip()
    client_id = os.environ.get("AZURE_CLIENT_ID", "").strip()
    if not tenant or not client_id:
        return None
    authority = azure_authority_url(tenant)
    cache_path = token_cache_path()
    cache = _load_cache(cache_path)
    app = msal.PublicClientApplication(
        client_id,
        authority=authority,
        token_cache=cache,
    )
    for account in app.get_accounts():
        r = app.acquire_token_silent(scopes, account=account)
        if r and r.get("access_token"):
            _save_cache(cache_path, cache)
            return r["access_token"]
    return None


def acquire_graph_token(
    scopes: list[str],
    *,
    emit: Callable[[str], None] | None = None,
) -> str:
    """Acquire access token (silent cache or device flow)."""
    emit = emit or (lambda msg: print(msg, flush=True))
    tenant = os.environ.get("AZURE_TENANT_ID", "").strip()
    client_id = os.environ.get("AZURE_CLIENT_ID", "").strip()
    if not tenant or not client_id:
        raise GraphSessionError(
            "Set AZURE_TENANT_ID and AZURE_CLIENT_ID (see integrations/outlook_graph/README.md)."
        )

    authority = azure_authority_url(tenant)
    cache_path = token_cache_path()
    cache = _load_cache(cache_path)
    app = msal.PublicClientApplication(
        client_id,
        authority=authority,
        token_cache=cache,
    )
    result = None
    for account in app.get_accounts():
        r = app.acquire_token_silent(scopes, account=account)
        if r and r.get("access_token"):
            result = r
            break
    if not result:
        flow = app.initiate_device_flow(scopes=scopes)
        if "user_code" not in flow:
            raise GraphSessionError(f"Device flow failed: {flow.get('error_description', flow)}")
        emit(flow["message"])
        result = app.acquire_token_by_device_flow(flow)
    _save_cache(cache_path, cache)

    if "access_token" not in result:
        desc = result.get("error_description", result)
        extra = ""
        if isinstance(desc, str) and "AADSTS9002332" in desc:
            extra = (
                "\n\nThis app is **single-tenant (Azure AD only)**. You cannot use AZURE_TENANT_ID=consumers with it. "
                "Either: (1) keep your org tenant GUID and sign in with a **member** M365 account, or (2) in Entra "
                "change **Supported account types** to include **personal Microsoft accounts** (or create a second "
                "app for personal mail) and then use consumers + that app's Client ID."
            )
        raise GraphSessionError(f"Auth failed: {desc}{extra}")
    return result["access_token"]


def graph_get_me(token: str) -> dict[str, Any]:
    root = graph_api_root()
    url = f"{root}/me"
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=60.0) as client:
        r = client.get(url, headers=headers)
        if r.status_code >= 400:
            raise GraphSessionError(
                f"Microsoft Graph HTTP {r.status_code} for {url}: {(r.text or '')[:2000]}"
            )
        return r.json()


def graph_list_messages(token: str, top: int) -> dict[str, Any]:
    root = graph_api_root()
    cache_path = token_cache_path()
    url = f"{root}/me/messages"
    params = {"$top": str(top), "$orderby": "receivedDateTime desc"}
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=60.0) as client:
        r = client.get(url, params=params, headers=headers)
        if r.status_code >= 400:
            body = (r.text or "").strip()[:4000]
            diag = _graph_response_diagnostics(r)
            probe = ""
            if r.status_code == 401:
                r_me = client.get(f"{root}/me", headers=headers)
                probe = (
                    f"\nDiagnostic: GET {root}/me → HTTP {r_me.status_code}. "
                    f"Body preview: {(r_me.text or '')[:400]!r}\n"
                )
                if r_me.status_code < 400:
                    guest_hint = ""
                    try:
                        me = r_me.json()
                        upn = (me.get("userPrincipalName") or "").upper()
                        mail = me.get("mail")
                        if "#EXT#" in upn:
                            guest_hint = (
                                "Likely cause: you are a **B2B guest** (#EXT# in userPrincipalName). "
                                "`/me/messages` is the mailbox **in the host tenant**, not your personal inbox.\n"
                                "Fix A — work mail: sign in with a **member** @company account that has M365 mail in that tenant.\n"
                                "Fix B — Hotmail/Outlook.com: in Entra set the app to allow **personal Microsoft accounts**; "
                                "set AZURE_TENANT_ID=consumers; clear token cache; complete device login with your "
                                "@outlook.com / @hotmail.com account (see README).\n"
                            )
                        elif not (isinstance(mail, str) and mail.strip()):
                            guest_hint = (
                                "Note: `/me` has **mail: null** — there may be **no Exchange mailbox** "
                                "for this user in this tenant.\n"
                            )
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        pass
                    probe += guest_hint + (
                        "Interpretation: token is accepted for profile but not for mail. "
                        "Other causes: Exchange **application access policy** blocking this app. "
                        "Ask your admin: https://learn.microsoft.com/graph/resolve-auth-errors\n"
                    )
                else:
                    probe += (
                        "Interpretation: Graph rejects this token on /me as well — wrong **GRAPH_API_ROOT** / "
                        "**AZURE_LOGIN_HOST** for your cloud (e.g. .us for GCC), clock skew, or network/proxy stripping auth.\n"
                    )
            hint = (
                f"If you changed API permissions or scopes, delete the cache file and sign in again: {cache_path}"
            )
            raise GraphSessionError(
                f"Microsoft Graph HTTP {r.status_code} for {r.request.url!s}.\n"
                f"Response body: {body or '(empty)'}\n"
                f"Response headers (subset): {diag}\n"
                f"{probe}"
                f"{hint}\n"
                "Confirm delegated Mail.Read + admin consent. For sovereign clouds set GRAPH_API_ROOT and "
                "AZURE_LOGIN_HOST (see README)."
            )
        return r.json()


def graph_send_mail(
    token: str,
    *,
    to_address: str,
    subject: str,
    body: str,
    is_html: bool = False,
) -> None:
    """POST /me/sendMail (requires Mail.Send on token)."""
    root = graph_api_root()
    url = f"{root}/me/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    content_type = "HTML" if is_html else "Text"
    recipients = [
        {"emailAddress": {"address": a.strip()}}
        for a in to_address.replace(";", ",").split(",")
        if a.strip()
    ]
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": recipients,
        },
        "saveToSentItems": True,
    }
    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, headers=headers, json=payload)
        if r.status_code not in (202, 200):
            raise GraphSessionError(
                f"sendMail failed HTTP {r.status_code}: {(r.text or '')[:2000]}"
            )


def jwt_claims_preview(token: str) -> dict[str, Any] | None:
    """Decode JWT payload for debugging (no signature verification)."""
    import base64

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")))
    except Exception:
        return None


def default_mail_read_scopes() -> list[str]:
    raw = os.environ.get("GRAPH_SCOPES", "").strip()
    return raw.split() if raw else list(DEFAULT_SCOPES_MAIL_READ)


def default_mail_send_scopes() -> list[str]:
    raw = os.environ.get("GRAPH_SCOPES", "").strip()
    if raw:
        return raw.split()
    return list(DEFAULT_SCOPES_MAIL_SEND)
