# LoRA / supervised fine-tuning (Llama 3.2)

This folder configures **[LlamaFactory](https://github.com/hiyouga/LlamaFactory)** (same project often called LLaMA-Factory) for **LoRA SFT** on your JSONL data, with **Weights & Biases** or **TensorBoard** during training. It does not change your Docker inference stack ([docker-compose.yml](../docker-compose.yml)); after training you merge/export separately if you want a new Ollama model.

## 1. Choose an environment

| Option | When to use |
|--------|-------------|
| **WSL2 (Ubuntu) + NVIDIA CUDA** | Recommended on Windows for stable PyTorch + GPU training. Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install), then Ubuntu, NVIDIA drivers for WSL, and CUDA per [NVIDIA WSL docs](https://docs.nvidia.com/cuda/wsl-user-guide/index.html). |
| **Native Windows venv** | If `nvidia-smi` works and you can install a CUDA-enabled PyTorch wheel from [pytorch.org](https://pytorch.org/get-started/locally/). |

Training **Llama 3.2 3B** with LoRA typically needs **~8 GB VRAM or more** (use smaller `per_device_train_batch_size`, higher `gradient_accumulation_steps`, or QLoRA in [configs/llama32_lora_sft.yaml](configs/llama32_lora_sft.yaml) if you hit OOM).

## 2. Python venv and PyTorch

From the **miLLM repo root** (or any working directory where paths in the YAML still make sense):

```bash
python -m venv .venv-train
source .venv-train/bin/activate   # Windows CMD: .venv-train\Scripts\activate.bat
```

Install **PyTorch with CUDA** first (pick the command that matches your CUDA version from [pytorch.org](https://pytorch.org/get-started/locally/)), then LlamaFactory and monitoring extras:

```bash
pip install -r training/requirements-train.txt
```

## 3. Hugging Face access (gated Llama weights)

The base model `meta-llama/Llama-3.2-3B-Instruct` is **gated** on Hugging Face.

1. Create a token at [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
2. Accept the **Llama 3.2** license on the model page.
3. Log in on the machine that will train:

```bash
huggingface-cli login
```

## 4. Prepare data

See [dataset/README.md](dataset/README.md). Put your ShareGPT-style rows in [dataset/train.jsonl](dataset/train.jsonl) (replace or extend the small starter file). For large corpora you can ignore git tracking via [.gitignore](../.gitignore) patterns and keep data elsewhere; point `file_name` in [dataset/dataset_info.json](dataset/dataset_info.json) if you use another path (same directory as `dataset_info.json` is simplest).

## 5. Monitoring

### Weights & Biases

```bash
export WANDB_API_KEY=...   # Windows PowerShell: $env:WANDB_API_KEY="..."
```

In [configs/llama32_lora_sft.yaml](configs/llama32_lora_sft.yaml), keep `report_to: wandb` and set `run_name` as you like. Open the run URL printed in the console during training.

### TensorBoard instead

In the same YAML, set `report_to: tensorboard` and define `logging_dir` (for example `training/runs/llama32-lora`). Then:

```bash
tensorboard --logdir training/runs
```

## 6. Run training

From **repo root** (so `training/dataset` paths resolve):

```bash
llamafactory-cli train training/configs/llama32_lora_sft.yaml
```

Checkpoints and logs go under `training/saves/` (see `output_dir` in the YAML).

## 7. After training (optional, not automated here)

Merge LoRA into the base model, convert to **GGUF**, and register with **Ollama** if you want the fine-tuned weights behind your existing LiteLLM route. See LlamaFactory docs for `llamafactory-cli export` and merge examples.
