"""
Summarize recent Outlook mail via Microsoft Graph + LiteLLM (OpenAI-compatible).

Uses MSAL device-code flow (public client). Register a single-tenant or
multi-tenant app in Entra ID with delegated Graph permissions (see README).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

from graph_session import (
    GraphSessionError,
    acquire_graph_token,
    default_mail_read_scopes,
    graph_list_messages,
    jwt_claims_preview,
    token_cache_path,
)


def _print_token_debug(token: str) -> None:
    claims = jwt_claims_preview(token)
    if not claims:
        print("GRAPH_DEBUG: could not decode access token as JWT.", flush=True)
        return
    preview = {
        "aud": claims.get("aud"),
        "iss": claims.get("iss"),
        "scp": claims.get("scp"),
        "roles": claims.get("roles"),
        "tid": claims.get("tid"),
        "appid": claims.get("appid"),
    }
    print(f"GRAPH_DEBUG (JWT claims, not the full token): {json.dumps(preview, indent=2)}", flush=True)


def litellm_chat_completion(system: str, user: str) -> str:
    base = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000").rstrip("/")
    key = (os.environ.get("LITELLM_API_KEY") or os.environ.get("LITELLM_MASTER_KEY") or "").strip()
    model = os.environ.get("LITELLM_MODEL", "llama3.2").strip()
    if not key:
        raise SystemExit("Set LITELLM_API_KEY or LITELLM_MASTER_KEY for LiteLLM.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    with httpx.Client(timeout=300.0) as client:
        r = client.post(
            f"{base}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if r.status_code >= 400:
            raise SystemExit(f"LiteLLM error {r.status_code}: {r.text[:2000]}")
        data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise SystemExit(f"Unexpected LiteLLM response: {json.dumps(data)[:1500]}") from e


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize recent Outlook messages via Graph + LiteLLM.")
    parser.add_argument("--top", type=int, default=5, help="Number of recent messages to fetch (default 5).")
    parser.add_argument(
        "--dry-graph",
        action="store_true",
        help="Only list message subjects from Graph (no LiteLLM call).",
    )
    cache_default = token_cache_path()
    parser.add_argument(
        "--clear-token-cache",
        action="store_true",
        help=f"Delete {cache_default.name} before signing in (use after permission or scope changes).",
    )
    args = parser.parse_args()

    cache_path = token_cache_path()
    if args.clear_token_cache and cache_path.exists():
        cache_path.unlink()
        print(f"Removed token cache: {cache_path}", flush=True)

    scopes = default_mail_read_scopes()

    print("Signing in to Microsoft Graph (device code)…", flush=True)
    try:
        token = acquire_graph_token(scopes)
    except GraphSessionError as e:
        raise SystemExit(str(e)) from e

    if os.environ.get("GRAPH_DEBUG", "").strip() in ("1", "true", "yes", "on"):
        _print_token_debug(token)

    print(f"Fetching up to {args.top} messages…", flush=True)
    try:
        data = graph_list_messages(token, args.top)
    except GraphSessionError as e:
        raise SystemExit(str(e)) from e
    messages = data.get("value") or []

    if args.dry_graph:
        for m in messages:
            print("-", m.get("subject") or "(no subject)")
        return

    system = (
        "You summarize work email for the user. Be concise, factual, and use bullet points when helpful. "
        "Do not invent content not present in the email."
    )
    for m in messages:
        subject = m.get("subject") or "(no subject)"
        preview = (m.get("bodyPreview") or "").strip()
        if not preview:
            preview = "(empty preview)"
        user_prompt = f"Subject: {subject}\n\nPreview/body:\n{preview[:16000]}"
        print(f"\n=== {subject} ===", flush=True)
        summary = litellm_chat_completion(system, user_prompt)
        print(summary, flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
