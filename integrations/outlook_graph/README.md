# Outlook (Microsoft Graph) + LiteLLM

Shared MSAL + Graph helpers live in [`graph_session.py`](graph_session.py) (used by `app.py` and by the **MCP** server in [../outlook_mcp/README.md](../outlook_mcp/README.md)).

Small CLI that:

1. Signs you in to **Microsoft Graph** with **MSAL device-code flow** (public client; no Azure client secret required).
2. Reads your **recent mail** (`GET /me/messages`).
3. Sends each message preview to **LiteLLM** (`POST /v1/chat/completions`) using the same model alias as Open WebUI (for example `llama3.2`).

Open WebUI stays a separate browser UI; this tool is for **mailbox + local LLM** automation.

## Prerequisites

- **Docker stack running** with LiteLLM reachable (default host: `http://localhost:4000`). See repo [README.md](../../README.md).
- **Ollama** + model configured in [litellm/config.yaml](../../litellm/config.yaml).
- **Python 3.11+** on the machine where you run the script (or use the optional Docker profile below).

## 1. Register an app in Microsoft Entra ID (Azure Portal)

Complete these in [Azure Portal](https://portal.azure.com/) → **Microsoft Entra ID** → **App registrations** → **New registration**.

1. **Name:** e.g. `miLLM Outlook Graph reader`.
2. **Supported account types:** choose what matches who will sign in:
   - **Work mail only:** *Accounts in this organizational directory only* (or multitenant org).
   - **Personal Hotmail / Outlook.com:** *Accounts in any organizational directory and personal Microsoft accounts* (or *Personal Microsoft accounts only*). Single-tenant org-only apps **cannot** sign in consumers.
3. **Redirect URI:** not required for **device code** flow with a public client. You can leave blank or add **Mobile and desktop applications** → `https://login.microsoftonline.com/common/oauth2/nativeclient` if the portal requires one.
4. After creation, copy:
   - **Application (client) ID** → `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → `AZURE_TENANT_ID`
5. Under **Authentication** → **Advanced settings** → allow **public client flows** = **Yes** (required for device code).

### API permissions

**API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**:

| Permission   | Purpose                          |
|-------------|-----------------------------------|
| `Mail.Read` | Read the signed-in user’s mail   |
| `User.Read` | Basic profile (`/me`)           |

Click **Grant admin consent for …** if your tenant requires it (common on work accounts).

> Use **`Mail.ReadWrite`** only if you later extend this app to create or modify messages.

## 2. Environment variables

Add to your repo **`.env`** (do not commit real values):

| Variable | Example | Notes |
|----------|---------|--------|
| `AZURE_TENANT_ID` | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | Entra **Directory (tenant) ID** for work mail. For **personal** Outlook.com / Hotmail use the literal value **`consumers`** (and an app that allows personal accounts). |
| `AZURE_CLIENT_ID` | `yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy` | App client ID |
| `LITELLM_BASE_URL` | `http://127.0.0.1:4000` | On host; in Docker profile use `http://litellm:4000` (set by compose) |
| `LITELLM_API_KEY` | `sk-…` | LiteLLM **virtual key** or same value as `LITELLM_MASTER_KEY` for private dev |
| `LITELLM_MODEL` | `llama3.2` | Must match a `model_name` in `litellm/config.yaml` |
| `GRAPH_SCOPES` | *(optional)* | Space-separated; default is `Mail.Read` + `User.Read` |
| `GRAPH_API_ROOT` | *(optional)* | Default `https://graph.microsoft.com/v1.0`. For **Azure US Government** use `https://graph.microsoft.us/v1.0` (and matching login host below). |
| `AZURE_LOGIN_HOST` | *(optional)* | Default `login.microsoftonline.com`. For US Gov use `login.microsoftonline.us` (must match your tenant cloud). After changing this, delete `token_cache.bin` and sign in again. |

## 3. Run on the host (recommended for device code)

```powershell
cd "C:\Users\has4e\Documents\Aramco Digital Projects\miLLM\integrations\outlook_graph"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Load AZURE_* and LITELLM_* from repo .env manually or:
Get-Content "..\..\.env" | ForEach-Object { if ($_ -match '^\s*([^#=]+)=(.*)$') { Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim() } }
python app.py --top 5
```

Follow the **device code** URL in the terminal, sign in, approve permissions. A token cache file `token_cache.bin` is written next to `app.py` (gitignored).

**Personal inbox (Hotmail / Outlook.com):** the app must list **personal Microsoft accounts** under *Supported account types*. Then set `AZURE_TENANT_ID` to **`consumers`**, run `python app.py --clear-token-cache …`, and sign in with your **@outlook.com / @hotmail.com** account. If sign-in returns **AADSTS9002332** (“Azure Active Directory users only … do not use the /consumers endpoint”), this registration is **org-only**—either change it in **App registration → Authentication** (if allowed) or create a **separate** app for personal mail and use its Client ID with `consumers`.

**Dry run (Graph only, no LLM):**

```powershell
python app.py --top 5 --dry-graph
```

## 4. Optional: Docker (same network as LiteLLM)

Device code needs an **interactive** terminal.

From the **repo root** (with `AZURE_TENANT_ID` and `AZURE_CLIENT_ID` set in `.env`):

```powershell
docker compose --profile outlook build outlook-graph-assistant
docker compose --profile outlook run --rm -it outlook-graph-assistant
```

Compose sets `LITELLM_BASE_URL=http://litellm:4000` and `LITELLM_API_KEY` from `LITELLM_MASTER_KEY`. Start the main stack first: `docker compose up -d`.

### Troubleshooting Graph `401` (especially empty body)

If `GRAPH_DEBUG` shows `Mail.Read` on the token but mail calls still return **401**:

1. Run again; the app prints a **diagnostic `GET /me`** result. If **`/me` succeeds** but **`/me/messages` fails**, your tenant often has an **Exchange application access policy** (or similar) that blocks this app from the mailbox API even though Entra shows `Mail.Read`. Your Exchange / Entra admin must allow the application (see [Resolve Microsoft Graph authorization errors](https://learn.microsoft.com/graph/resolve-auth-errors)).
2. If **GET `/me` also returns 401**, you may be on a **national cloud** (wrong Graph host). Set `GRAPH_API_ROOT` and `AZURE_LOGIN_HOST` for your cloud, remove `token_cache.bin`, and sign in again.
3. Confirm the signed-in user has an **Exchange Online** mailbox (not only on-premises without the right hybrid setup).
4. If **`userPrincipalName` contains `#EXT#`**, you are a **guest** in that tenant. **`/me/messages`** is the mailbox **in that tenant**, not your personal Hotmail/Outlook.com inbox. Use a **work (member) account** with M365 mail, or a different app registration / sign-in path for **consumer-only** scenarios.

## Compliance

Mail content is sent to your **local** LiteLLM → **Ollama** path. Follow your organization’s policies on **data residency**, **logging**, and **model use** before processing real mail.
