# Fast Fine-Tuning Setup and Training Guide

This guide will help you set up and run the fast fine-tuning process for improving MCP tool usage with your LLM.

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Create training environment
python -m venv .venv-train
source .venv-train/bin/activate  # Linux/Mac
# OR
.venv-train\Scripts\activate.bat  # Windows CMD
# OR  
.venv-train\Scripts\Activate.ps1  # Windows PowerShell

# Install PyTorch with CUDA (adjust for your CUDA version)
# For CUDA 11.8:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1:
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# For CPU-only (slower):
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install LlamaFactory and dependencies
pip install -r training/requirements-train.txt
```

### 2. Hugging Face Setup

```bash
# Login to Hugging Face (required for Llama 3.2)
huggingface-cli login

# Accept Llama 3.2 license at: https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
```

### 3. Run Fast Training

```bash
# From the repo root directory
llamafactory-cli train training/configs/mcp_fast_sft.yaml
```

**Expected Training Time:** 45-75 minutes on 8GB GPU

### 4. Export the Model

```bash
# After training completes
llamafactory-cli export training/configs/export_mcp.yaml
```

### 5. Create Ollama Model

Create a `Modelfile` in your training directory:

```dockerfile
FROM training/saves/mcp-tool-merged

# Optional: Add a system message
SYSTEM """
You are a professional email assistant integrated with Microsoft Outlook via MCP tools. 
When users ask about emails, retrieve them using the available tools and present the information clearly and concisely. 
Never generate code when you can use the available tools.
"""

PARAMETER temperature 0.7
PARAMETER top_p 0.9
```

Then create the model:

```bash
cd training/saves/mcp-tool-merged
ollama create mcp-tool-assistant -f Modelfile
```

### 6. Update LiteLLM Configuration

Add to your `litellm/config.yaml`:

```yaml
model_list:
  - model_name: mcp-tool-assistant
    litellm_params:
      model: ollama/mcp-tool-assistant
      api_base: http://localhost:11434
      api_key: dummies
```

### 7. Test the Fine-Tuned Model

Restart your Docker services and test with Open WebUI:

```bash
docker compose restart litellm open-webui
```

## 📊 Training Configuration Details

### Fast Training Optimizations

- **QLoRA (4-bit quantization)**: Reduces VRAM usage and speeds up training
- **Batch size 2**: Increased from 1 for faster processing
- **Gradient accumulation 4**: Balanced for memory efficiency
- **Higher learning rate (1e-4)**: Faster convergence
- **Fewer epochs (2)**: Sufficient for 25 examples
- **Shorter context (1024)**: Faster processing
- **Gradient checkpointing**: Memory optimization

### Monitoring Training

Training progress will be logged to:
- **TensorBoard**: `training/runs/mcp-tool-fast`
- **Console output**: Real-time loss and metrics

To view TensorBoard:
```bash
tensorboard --logdir training/runs
```

## 🔧 Troubleshooting

### Common Issues

1. **CUDA Out of Memory**
   - Reduce `per_device_train_batch_size` to 1
   - Increase `gradient_accumulation_steps` to 8
   - Ensure `gradient_checkpointing: true` is set

2. **Hugging Face Authentication**
   - Run `huggingface-cli login`
   - Accept the Llama 3.2 license on the website
   - Verify your token has read access

3. **Slow Training**
   - Ensure CUDA is working: `python -c "import torch; print(torch.cuda.is_available())"`
   - Check GPU memory usage
   - Consider using QLoRA if VRAM is limited

4. **Training Fails**
   - Check dataset format in `training/dataset/mcp_tool_sft.jsonl`
   - Verify all required fields are present
   - Ensure dataset is registered in `dataset_info.json`

### Performance Tips

- **Use SSD storage** for faster I/O
- **Close other GPU applications** during training
- **Monitor VRAM usage** to avoid OOM errors
- **Use TensorBoard** to track training progress

## 🎯 Expected Results

After fine-tuning, your LLM should:

✅ **Present email data clearly** instead of generating code  
✅ **Format responses professionally** with proper structure  
✅ **Handle all MCP tools** appropriately  
✅ **Maintain context** across multi-turn conversations  
✅ **Provide helpful summaries** of email content  

## 📝 Dataset Information

The training dataset (`training/dataset/mcp_tool_sft.jsonl`) contains 25 examples covering:

- **10 examples** for `outlook_list_recent` (email retrieval)
- **8 examples** for `outlook_send` (email sending)
- **4 examples** for `outlook_login` (authentication)
- **3 examples** for multi-turn conversations

Each example follows the ShareGPT format with user queries and assistant responses that demonstrate proper MCP tool usage.

## 🔄 Next Steps

1. **Test the model** with various email queries
2. **Adjust prompts** if needed for better results
3. **Consider additional training** if specific scenarios need improvement
4. **Monitor performance** in real usage

## 📚 Additional Resources

- [LlamaFactory Documentation](https://llamafactory.readthedocs.io/)
- [QLoRA Paper](https://arxiv.org/abs/2305.14314)
- [Hugging Face Transformers](https://huggingface.co/docs/transformers/index)
- [Ollama Documentation](https://ollama.com/library)

## 🤝 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the training logs for error messages
3. Verify your environment setup
4. Consult the LlamaFactory documentation