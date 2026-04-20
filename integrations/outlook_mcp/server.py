"""
Outlook / Microsoft Graph MCP server (Streamable HTTP) for Open WebUI.

Run with transport streamable-http (see __main__). MSAL + Graph helpers: outlook_mcp.graph_session.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Annotated

from mcp.server.fastmcp import FastMCP

from outlook_mcp.graph_session import (
    GraphSessionError,
    acquire_graph_token,
    complete_device_flow_from_chat,
    default_mail_send_scopes,
    graph_list_messages,
    graph_send_mail,
    start_device_flow_for_chat,
    try_acquire_token_silent,
)


def _emit(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _scopes() -> list[str]:
    return default_mail_send_scopes()


def _token_or_raise() -> str:
    tok = try_acquire_token_silent(_scopes())
    if not tok:
        raise GraphSessionError(
            "No cached Microsoft session. Run tool **outlook_login** first (device code in server logs), "
            "then retry."
        )
    return tok


port = int(os.environ.get("MCP_HTTP_PORT", "8010"))
host = os.environ.get("MCP_HTTP_HOST", "0.0.0.0")

mcp = FastMCP(
    "OutlookGraph",
    instructions=(
        "Microsoft Outlook via Graph: outlook_login_start then outlook_login_finish (recommended for Open WebUI), "
        "or outlook_login once; then outlook_list_recent, outlook_send. Requires AZURE_TENANT_ID and AZURE_CLIENT_ID."
    ),
    host=host,
    port=port,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
async def outlook_login() -> str:
    """
    Sign in to Microsoft Graph (device code flow) in one call. The URL and code are printed to
    **container stderr** — in Open WebUI you often see nothing until this finishes. Prefer
    **outlook_login_start** then **outlook_login_finish** so the device code appears in chat.
    """
    try:
        await asyncio.to_thread(acquire_graph_token, _scopes(), emit=_emit)
    except GraphSessionError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
    return json.dumps(
        {
            "ok": True,
            "message": (
                "Microsoft sign-in completed. Token cached for this server. "
                "If you did not see a device code, check `docker compose logs outlook-mcp`."
            ),
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def outlook_login_start() -> str:
    """
    Step 1 of 2: start device-code sign-in. Returns user_code, verification_uri, and login_id in JSON.
    Open the URI in a browser, enter the code, then call outlook_login_finish(login_id).
    """
    try:
        data = await asyncio.to_thread(start_device_flow_for_chat, _scopes())
    except GraphSessionError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
    return json.dumps({"ok": True, **data}, ensure_ascii=False)


@mcp.tool()
async def outlook_login_finish(
    login_id: Annotated[str, "Value from outlook_login_start (field login_id)"],
) -> str:
    """
    Step 2 of 2: complete device login after approving in the browser. Blocks until Microsoft confirms
    or the flow times out.
    """
    try:
        await asyncio.to_thread(complete_device_flow_from_chat, login_id.strip())
    except GraphSessionError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
    return json.dumps(
        {
            "ok": True,
            "message": "Microsoft sign-in completed. Token cached for this server.",
        },
        ensure_ascii=False,
    )


@mcp.tool()
async def outlook_list_recent(
    top: Annotated[int, "Max messages to return (default 10, cap 50)"] = 10,
) -> str:
    """List recent inbox messages (subject, preview, id). Requires prior outlook_login."""
    top = max(1, min(top, 50))
    try:
        try:
            token = _token_or_raise()
        except GraphSessionError as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        data = await asyncio.to_thread(graph_list_messages, token, top)
    except GraphSessionError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
    rows = []
    for m in data.get("value") or []:
        rows.append(
            {
                "id": m.get("id"),
                "subject": m.get("subject"),
                "receivedDateTime": m.get("receivedDateTime"),
                "preview": (m.get("bodyPreview") or "")[:500],
            }
        )
    return json.dumps({"ok": True, "count": len(rows), "messages": rows}, ensure_ascii=False)


@mcp.tool()
async def outlook_send(
    to_address: Annotated[str, "Recipient email(s); comma or semicolon separated"],
    subject: Annotated[str, "Email subject"],
    body: Annotated[str, "Plain text or HTML body"],
    is_html: Annotated[bool, "True if body is HTML"] = False,
) -> str:
    """Send an email via Graph sendMail. Requires Mail.Send and prior outlook_login."""
    try:
        try:
            token = _token_or_raise()
        except GraphSessionError as e:
            return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
        await asyncio.to_thread(
            graph_send_mail,
            token,
            to_address=to_address,
            subject=subject,
            body=body,
            is_html=is_html,
        )
    except GraphSessionError as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
    return json.dumps({"ok": True, "message": f"Message sent to {to_address}."}, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
