# miLLM: local Ollama + LiteLLM + Open WebUI

This repo runs **LiteLLM Proxy** (with Postgres for virtual keys) and **Open WebUI** in Docker. **Ollama** runs on your machine separately and serves the model; containers reach it at `host.docker.internal:11434` (Docker Desktop on Windows, or Linux with `extra_hosts` as in [docker-compose.yml](docker-compose.yml)).

## Prerequisites

1. **Docker Desktop** (or Docker Engine + Compose v2) with Compose available as `docker compose`.
2. **Ollama** installed on the host: [https://ollama.com/](https://ollama.com/)
3. Pull at least one model that matches [litellm/config.yaml](litellm/config.yaml), for example:

```bash
ollama pull llama3.2
```

If you use a different tag (for example `llama3.2:latest`), ensure the `model:` line under `litellm_params` matches what Ollama expects (see `ollama list`).

## Quick start

1. Copy environment file and edit secrets:

```powershell
Copy-Item .env.example .env
```

Set `LITELLM_MASTER_KEY` to a long random string starting with `sk-`. Set `WEBUI_SECRET_KEY` and a strong `POSTGRES_PASSWORD` if the stack is reachable beyond localhost.

2. Start Ollama on the host (leave it running).

3. Start the stack from this directory:

```powershell
docker compose up -d
```

4. **LiteLLM UI:** [http://localhost:4000/ui](http://localhost:4000/ui) — log in with your `LITELLM_MASTER_KEY` when prompted (admin). Create a **team** and a **virtual key**, and grant that key access to the model alias(es) defined in `litellm/config.yaml` (for example `llama3.2`).

5. **Open WebUI:** [http://localhost:3000](http://localhost:3000) — complete first-time admin signup.

## LLM in Open WebUI (automatic)

[docker-compose.yml](docker-compose.yml) sets **Open WebUI** to use the **OpenAI-compatible** endpoint at **`http://litellm:4000/v1`** with **`OPENAI_API_KEY`** set from your **`LITELLM_MASTER_KEY`**. On a **first** install, Open WebUI should pick that up from the environment (see Open WebUI docs on `PersistentConfig` if you already had a volume from an older run).

1. Start the stack, open [http://localhost:3000](http://localhost:3000), sign in.
2. In chat, choose the model name that matches LiteLLM (for example **`llama3.2`** from [litellm/config.yaml](litellm/config.yaml)) and send a message.

`ENABLE_OLLAMA_API` is set to **`false`** so Open WebUI does not try to talk to host Ollama from inside Docker by default; traffic goes **Open WebUI → LiteLLM → Ollama** as designed.

### Optional: virtual key instead of master key

For teams or tighter key scope, create a **virtual key** in [http://localhost:4000/ui](http://localhost:4000/ui), then in Open WebUI use **Admin** → **Connections** and set the OpenAI-compatible **API key** (and URL if needed) to that virtual key. That overrides the persisted “OpenAI” settings stored by Open WebUI.

### Manual connection (if env-based setup is ignored)

If a previous Open WebUI database already persisted other URLs, either clear the **`open_webui_data`** volume for a fresh config, set **`ENABLE_PERSISTENT_CONFIG=False`** in compose (Open WebUI will always read env; UI changes do not survive restart), or edit connections in the UI:

1. **Settings** → **Connections** (or **Admin** → **Connections**).
2. **OpenAI API** — **Base URL** `http://litellm:4000/v1` (or `http://localhost:4000/v1` if requests originate from the browser).
3. **API Key** — LiteLLM **virtual key** (or master key for private dev only).
4. Pick model **`llama3.2`** (or your configured alias) in the model dropdown.

## Per-user usage tracking (optional)

This compose file sets `ENABLE_FORWARD_USER_INFO_HEADERS=true` for Open WebUI. [litellm/config.yaml](litellm/config.yaml) maps `X-OpenWebUI-User-Id` and `X-OpenWebUI-User-Email` and tags spend with `X-OpenWebUI-User-Name` so LiteLLM can attribute usage across multiple Open WebUI accounts. See [Open WebUI | LiteLLM](https://docs.litellm.ai/docs/tutorials/openweb_ui).

## LM Studio instead of Ollama

Run LM Studio’s local server on a port (for example `1234`), then add a `model_list` entry with `api_base` pointing at `http://host.docker.internal:1234/v1` and `model: openai/<id-as-shown-by-lmstudio>` (OpenAI-compatible pattern). Remove or keep Ollama entries as needed.

## Fine-tuning (LoRA / SFT)

For local **LoRA supervised fine-tuning** of Llama 3.2 with **W&B or TensorBoard** during training, see [training/README.md](training/README.md) and [training/configs/llama32_lora_sft.yaml](training/configs/llama32_lora_sft.yaml).

## Outlook (Microsoft Graph) + LiteLLM

To read recent **Outlook** mail via **Microsoft Graph** and summarize it with the **same LiteLLM** stack as Open WebUI, see [integrations/outlook_graph/README.md](integrations/outlook_graph/README.md). Optional Docker profile **`outlook`** builds `outlook-graph-assistant`; run it interactively with `docker compose --profile outlook run --rm -it outlook-graph-assistant` after `docker compose up -d`.

For **Open WebUI External Tools (MCP Streamable HTTP)**, the **`outlook-mcp`** service exposes Graph mail tools at `http://outlook-mcp:8010/mcp` — see [integrations/outlook_mcp/README.md](integrations/outlook_mcp/README.md). It starts with `docker compose up -d` alongside Open WebUI.

## Files

| File | Purpose |
|------|--------|
| [docker-compose.yml](docker-compose.yml) | Postgres, LiteLLM database image, Open WebUI |
| [litellm/config.yaml](litellm/config.yaml) | Model routes, DB and master key via env, header mappings |
| [.env.example](.env.example) | Template for secrets and Postgres settings |
| [integrations/outlook_graph/](integrations/outlook_graph/) | Graph + LiteLLM mail summarizer (CLI; optional Compose profile `outlook`) |
