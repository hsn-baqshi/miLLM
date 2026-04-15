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

## Connect Open WebUI to LiteLLM

In Open WebUI:

1. Open **Settings** → **Connections** (or **Admin** → **Connections**, depending on version).
2. Add an **OpenAI**-compatible connection (or “OpenAI API”).
3. Set **API Base URL** to `http://litellm:4000` so traffic stays on the Docker network between the Open WebUI and LiteLLM containers.
4. Set **API Key** to the **virtual key** you created in the LiteLLM UI (not the master key for day-to-day chat).
5. Save, then pick the routed model name (for example `llama3.2`) in the chat model dropdown and send a test message.

If your Open WebUI build resolves connections from the browser instead of the server, try `http://localhost:4000` as the base URL instead.

## Per-user usage tracking (optional)

This compose file sets `ENABLE_FORWARD_USER_INFO_HEADERS=true` for Open WebUI. [litellm/config.yaml](litellm/config.yaml) maps `X-OpenWebUI-User-Id` and `X-OpenWebUI-User-Email` and tags spend with `X-OpenWebUI-User-Name` so LiteLLM can attribute usage across multiple Open WebUI accounts. See [Open WebUI | LiteLLM](https://docs.litellm.ai/docs/tutorials/openweb_ui).

## LM Studio instead of Ollama

Run LM Studio’s local server on a port (for example `1234`), then add a `model_list` entry with `api_base` pointing at `http://host.docker.internal:1234/v1` and `model: openai/<id-as-shown-by-lmstudio>` (OpenAI-compatible pattern). Remove or keep Ollama entries as needed.

## Fine-tuning (LoRA / SFT)

For local **LoRA supervised fine-tuning** of Llama 3.2 with **W&B or TensorBoard** during training, see [training/README.md](training/README.md) and [training/configs/llama32_lora_sft.yaml](training/configs/llama32_lora_sft.yaml).

## Files

| File | Purpose |
|------|--------|
| [docker-compose.yml](docker-compose.yml) | Postgres, LiteLLM database image, Open WebUI |
| [litellm/config.yaml](litellm/config.yaml) | Model routes, DB and master key via env, header mappings |
| [.env.example](.env.example) | Template for secrets and Postgres settings |
