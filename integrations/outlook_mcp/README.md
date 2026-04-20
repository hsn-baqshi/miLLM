# Outlook MCP (Microsoft Graph) for Open WebUI

**MCP** server using **Streamable HTTP** so [Open WebUI](https://openwebui.com/) can attach Graph mail tools (`outlook_login`, `outlook_list_recent`, `outlook_send`). MSAL + Graph logic lives in [`graph_session.py`](graph_session.py) in this package.

## Prerequisites

- **Entra app** (see below): public client flows, delegated **Mail.Read**, **Mail.Send**, **User.Read**, admin consent as needed.
- Repo **`.env`** with at least `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` (and the rest of your stack: `LITELLM_MASTER_KEY`, `WEBUI_SECRET_KEY`, …).

## Register an app in Microsoft Entra ID

In [Azure Portal](https://portal.azure.com/) → **Microsoft Entra ID** → **App registrations** → **New registration**:

1. **Name:** e.g. `miLLM Outlook MCP`.
2. **Supported account types:** match who will sign in:
   - **Work mail only:** *Accounts in this organizational directory only* (or multitenant org).
   - **Personal Hotmail / Outlook.com:** *Accounts in any organizational directory and personal Microsoft accounts* (or *Personal Microsoft accounts only*). Single-tenant org-only apps **cannot** sign in consumers.
3. **Redirect URI:** not required for **device code** with a public client. You can leave blank or add **Mobile and desktop applications** → `https://login.microsoftonline.com/common/oauth2/nativeclient` if the portal requires one.
4. After creation, copy **Application (client) ID** → `AZURE_CLIENT_ID`, **Directory (tenant) ID** → `AZURE_TENANT_ID`.
5. Under **Authentication** → **Advanced settings** → **Allow public client flows** = **Yes** (required for device code).

### API permissions

**API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**:

| Permission    | Purpose                        |
|---------------|--------------------------------|
| `Mail.Read`   | Read the signed-in user’s mail |
| `Mail.Send`   | Send mail (MCP `outlook_send`) |
| `User.Read`   | Basic profile (`/me`)          |

Click **Grant admin consent** if your tenant requires it.

## Run with Docker Compose

From the **repo root**:

```powershell
docker compose build outlook-mcp
docker compose up -d outlook-mcp open-webui
```

The service listens on **`0.0.0.0:8010`** inside the compose network (override host port with **`OUTLOOK_MCP_HTTP_PORT`** in [docker-compose.yml](../../docker-compose.yml) → maps to **`MCP_HTTP_PORT`** in the container).

MSAL token cache is persisted on volume **`outlook_mcp_msal`** at **`MSAL_TOKEN_CACHE_PATH=/data/msal_token_cache.bin`**.

## Wire Open WebUI

1. Open **http://localhost:3000** → **Admin** → **External Tools** (or **Settings** → tools / MCP, depending on version).
2. **Add server** → type **MCP (Streamable HTTP)**.
3. **Server URL:** `http://outlook-mcp:8010/mcp`  
   - Use the **internal** hostname `outlook-mcp` (same Docker network as Open WebUI), not `localhost`.
4. Authentication: **None** (trusted local network only). For production, put a reverse proxy and auth in front of MCP.
5. Save and restart Open WebUI if prompted. Keep **`WEBUI_SECRET_KEY`** stable so encrypted settings do not break.

### First-time sign-in

Open WebUI does **not** show the Microsoft device URL/code in chat if you only use **`outlook_login`** (that text goes to **container stderr**). Use the two-step flow so the model returns the code in the tool result:

1. In chat (with MCP tools enabled for the model), call **`outlook_login_start`**. The JSON response includes **`verification_uri`**, **`user_code`**, and **`login_id`**.
2. Open the verification URI in a browser, enter the code, approve permissions.
3. Call **`outlook_login_finish`** with the same **`login_id`**. This step blocks until Microsoft confirms sign-in or the flow expires.
4. Call **`outlook_list_recent`** / **`outlook_send`** as needed.

**Alternative (Docker / logs):** invoke **`outlook_login`** once and watch **`docker compose logs -f outlook-mcp`** for the URL and code in stderr, then wait for the tool to return.

**Personal inbox (Hotmail / Outlook.com):** the app must allow **personal Microsoft accounts**. Set `AZURE_TENANT_ID` to **`consumers`**, clear the token cache (delete the cache file or remove the volume), complete device login with **@outlook.com / @hotmail.com**. If sign-in returns **AADSTS9002332** (“Azure Active Directory users only … do not use the /consumers endpoint”), the registration is **org-only**—change **Supported account types** in Entra (if allowed) or create a **separate** app for personal mail and use its Client ID with `consumers`.

## Troubleshooting sendMail **HTTP 400**

Graph returns **400** when the request body is invalid. Typical causes:

- **No usable recipients** after parsing `to_address` (empty string, only commas, etc.).
- **Invalid SMTP address** — typos, spaces inside the address, or a display string without a valid email.
- **Recipients like `Name <user@domain.com>`** — supported; the address inside `<…>` is extracted automatically.

After rebuilding `outlook-mcp`, the **`outlook_send`** tool error JSON includes Graph’s **`code`** and **`message`** plus the recipient list that was sent. Fix the addresses or subject/body and retry.

## Troubleshooting Graph `401` (especially empty body)

If mail calls return **401** even though permissions look correct:

1. If **GET `/me` succeeds** but **`/me/messages` fails**, your tenant may have an **Exchange application access policy** blocking this app. Your Exchange / Entra admin must allow the application ([Resolve Microsoft Graph authorization errors](https://learn.microsoft.com/graph/resolve-auth-errors)).
2. If **GET `/me` also returns 401**, you may be on a **national cloud** (wrong Graph host). Set `GRAPH_API_ROOT` and `AZURE_LOGIN_HOST` for your cloud, remove the token cache, and sign in again.
3. Confirm the signed-in user has an **Exchange Online** mailbox.
4. If **`userPrincipalName` contains `#EXT#`**, you are a **guest** in that tenant. **`/me/messages`** is the mailbox **in that tenant**, not a personal Hotmail/Outlook.com inbox. Use a **member** work account, or an app + `consumers` path for consumer mail.

## Open WebUI + Streamable HTTP quirks

Some Open WebUI versions had issues with certain Streamable HTTP modes; this server uses **stateless HTTP** + **JSON responses** (`json_response=True`) for broader compatibility. If connection still fails, see [Open WebUI MCP docs](https://docs.openwebui.com/features/extensibility/mcp/) and [open-webui#14762](https://github.com/open-webui/open-webui/issues/14762). A fallback is to run **[mcpo](https://github.com/open-webui/mcpo)** in front of a stdio MCP (not shipped here).

## Local run (without Docker)

From **`integrations`** (compose build context; parent of `outlook_mcp`):

```powershell
$env:PYTHONPATH = (Resolve-Path .).Path
$env:AZURE_TENANT_ID = "your-tenant-or-consumers"
$env:AZURE_CLIENT_ID = "your-client-id"
pip install -r outlook_mcp/requirements.txt
python -m outlook_mcp.server
```

Set **`MSAL_TOKEN_CACHE_PATH`** to a writable file if you like. Point Open WebUI on the host to `http://127.0.0.1:8010/mcp`.

## Environment variables

| Variable | Default | Notes |
|----------|---------|--------|
| `AZURE_TENANT_ID` | *(required)* | Org tenant GUID, or **`consumers`** for personal accounts (app must allow them) |
| `AZURE_CLIENT_ID` | *(required)* | |
| `AZURE_LOGIN_HOST` | `login.microsoftonline.com` | National cloud if needed (e.g. `.us` for GCC) |
| `GRAPH_API_ROOT` | `https://graph.microsoft.com/v1.0` | Match your cloud |
| `GRAPH_SCOPES` | *(optional)* | Space-separated; default includes Mail.Read + Mail.Send + User.Read |
| `MSAL_TOKEN_CACHE_PATH` | `token_cache.bin` next to `graph_session.py` | In Docker: `/data/msal_token_cache.bin` |
| `MCP_HTTP_PORT` | `8010` | Compose sets from `OUTLOOK_MCP_HTTP_PORT` |
| `MCP_HTTP_HOST` | `0.0.0.0` | |

## Compliance

Mail content flows through this MCP server to Microsoft Graph. Follow your organization’s policies on data handling and logging.
