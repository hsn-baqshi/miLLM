# Outlook MCP (Microsoft Graph) for Open WebUI

Small **MCP** server using **Streamable HTTP** so [Open WebUI](https://openwebui.com/) can attach Graph mail tools (`outlook_login`, `outlook_list_recent`, `outlook_send`). It reuses the same MSAL + Graph logic as [../outlook_graph/graph_session.py](../outlook_graph/graph_session.py).

## Prerequisites

- Same **Entra app** setup as [../outlook_graph/README.md](../outlook_graph/README.md): public client flows, delegated **Mail.Read**, **Mail.Send**, **User.Read**, admin consent as needed.
- Repo **`.env`** with at least `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` (and the rest of your stack: `LITELLM_MASTER_KEY`, `WEBUI_SECRET_KEY`, …).

## Run with Docker Compose

From the **repo root**:

```powershell
docker compose build outlook-mcp
docker compose up -d outlook-mcp open-webui
```

The service listens on **`0.0.0.0:8010`** inside the compose network (override host port with env **`OUTLOOK_MCP_HTTP_PORT`** in [docker-compose.yml](../../docker-compose.yml) → maps to **`MCP_HTTP_PORT`** in the container).

MSAL token cache is persisted on volume **`outlook_mcp_msal`** at **`MSAL_TOKEN_CACHE_PATH=/data/msal_token_cache.bin`**.

## Wire Open WebUI

1. Open **http://localhost:3000** → **Admin** → **External Tools** (or **Settings** → tools / MCP, depending on version).
2. **Add server** → type **MCP (Streamable HTTP)**.
3. **Server URL:** `http://outlook-mcp:8010/mcp`  
   - Use the **internal** hostname `outlook-mcp` (same Docker network as Open WebUI), not `localhost`.
4. Authentication: **None** (trusted local network only). For production, put a reverse proxy and auth in front of MCP.
5. Save and restart Open WebUI if prompted. Keep **`WEBUI_SECRET_KEY`** stable so encrypted settings do not break.

### First-time sign-in

1. In chat (with MCP tools enabled for the model), invoke tool **`outlook_login`** once, **or** watch logs while something triggers it:

   ```powershell
   docker compose logs -f outlook-mcp
   ```

2. Complete **device code** sign-in in the browser (URL + code appear in **container stderr**).
3. Call **`outlook_list_recent`** then **`outlook_send`** as needed.

If **`outlook_list_recent`** returns Graph errors about guests or mailboxes, see the troubleshooting section in [../outlook_graph/README.md](../outlook_graph/README.md) (same `/me` vs `/me/messages` behavior).

## Open WebUI + Streamable HTTP quirks

Some Open WebUI versions had issues with certain Streamable HTTP modes; this server uses **stateless HTTP** + **JSON responses** (`json_response=True`) for broader compatibility. If connection still fails, see [Open WebUI MCP docs](https://docs.openwebui.com/features/extensibility/mcp/) and [open-webui#14762](https://github.com/open-webui/open-webui/issues/14762). A fallback is to run **[mcpo](https://github.com/open-webui/mcpo)** in front of a stdio MCP (not shipped here).

## Local run (without Docker)

From **`integrations`** (parent of `outlook_graph`):

```powershell
$env:PYTHONPATH = (Resolve-Path .).Path
$env:AZURE_TENANT_ID = "your-tenant-or-consumers"
$env:AZURE_CLIENT_ID = "your-client-id"
pip install -r outlook_mcp/requirements.txt
python outlook_mcp/server.py
```

Set **`MSAL_TOKEN_CACHE_PATH`** to a writable file if you like. Then point Open WebUI (if it runs on the host) to `http://127.0.0.1:8010/mcp`.

## Environment variables

| Variable | Default | Notes |
|----------|---------|--------|
| `AZURE_TENANT_ID` | *(required)* | Same as Outlook Graph CLI |
| `AZURE_CLIENT_ID` | *(required)* | |
| `AZURE_LOGIN_HOST` | `login.microsoftonline.com` | National cloud if needed |
| `GRAPH_API_ROOT` | `https://graph.microsoft.com/v1.0` | |
| `GRAPH_SCOPES` | *(optional)* | Space-separated; default includes Mail.Read + Mail.Send + User.Read for MCP |
| `MSAL_TOKEN_CACHE_PATH` | `./token_cache.bin` relative to graph_session default | In Docker: `/data/msal_token_cache.bin` |
| `MCP_HTTP_PORT` | `8010` | Compose sets from `OUTLOOK_MCP_HTTP_PORT` |
| `MCP_HTTP_HOST` | `0.0.0.0` | |

## Compliance

Mail content flows through this MCP server to Microsoft Graph. Follow your organization’s policies on data handling and logging.
