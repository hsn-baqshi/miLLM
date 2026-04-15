# SFT dataset format (LlamaFactory)

This repo registers one custom dataset **`millm_sft`** in [dataset_info.json](dataset_info.json). It uses **ShareGPT-style** JSONL: one JSON object per line, with a **`messages`** array of turns.

Each turn is an object with:

- `role`: `user` or `assistant` (optional `system` if you extend the config)
- `content`: the text for that turn

## Example

See [example.jsonl](example.jsonl). Training reads **[train.jsonl](train.jsonl)** by default (starter lines are committed; replace with your full dataset for real runs).

## Converting from “OpenAI” chat exports

If you have `{"role":"...","content":"..."}` messages, you can use the same structure as long as `role` is `user` / `assistant` / `system` and `content` holds the text. The `dataset_info.json` tags map `user` / `assistant` to LlamaFactory’s ShareGPT parser.

## Registering more files

Add another key to `dataset_info.json` with a different `file_name`, then reference it in the YAML `dataset:` field (comma-separated for mixing datasets).
