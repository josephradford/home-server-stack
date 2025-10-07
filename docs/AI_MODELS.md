# AI Models Guide

Comprehensive guide to managing Ollama AI models in your home server.

## Pre-installed Models

Two models are automatically downloaded during initial setup:

### deepseek-coder:6.7b
- **Size:** 4.8 GB
- **RAM Required:** 6-8 GB
- **Use Case:** Code generation, debugging, technical documentation
- **Quantization:** 4-bit (optimized for home servers)
- **Strengths:**
  - Excellent at code completion
  - Strong understanding of programming concepts
  - Good balance of performance vs. accuracy

### llama3.2:3b
- **Size:** 2.0 GB
- **RAM Required:** 3-4 GB
- **Use Case:** General chat, simple Q&A, lightweight tasks
- **Quantization:** 4-bit
- **Strengths:**
  - Fast inference
  - Low resource usage
  - Good for quick interactions

## Managing Models

### List Models

```bash
# List all downloaded models
docker exec ollama ollama list

# Show model details
docker exec ollama ollama show deepseek-coder:6.7b

# Check running models
docker exec ollama ollama ps
```

### Download Models

```bash
# Pull a model
docker exec ollama ollama pull model-name:tag

# Examples
docker exec ollama ollama pull llama3:8b
docker exec ollama ollama pull codellama:13b
docker exec ollama ollama pull mistral:7b
```

**Note:** Large models can take 10-30 minutes to download depending on your internet speed.

### Remove Models

```bash
# Remove a model
docker exec ollama ollama rm model-name:tag

# Example
docker exec ollama ollama rm llama3:70b
```

### Copy/Rename Models

```bash
# Create a copy with different name
docker exec ollama ollama cp source-model:tag new-name:tag

# Example (useful for custom configurations)
docker exec ollama ollama cp llama3.2:3b my-chat-bot:latest
```

## Recommended Models by Use Case

### For Coding (8-16 GB RAM)

| Model | Size | RAM | Best For |
|-------|------|-----|----------|
| **deepseek-coder:6.7b** ✅ | 4.8 GB | 6-8 GB | General coding (pre-installed) |
| **codellama:7b** | 3.8 GB | 6 GB | Code generation, Meta model |
| **codellama:13b** | 7.4 GB | 12 GB | Advanced coding (slower) |
| **starcoder2:7b** | 4.0 GB | 6 GB | Multi-language code |

### For Chat (8-16 GB RAM)

| Model | Size | RAM | Best For |
|-------|------|-----|----------|
| **llama3.2:3b** ✅ | 2.0 GB | 3-4 GB | Quick chat (pre-installed) |
| **llama3:8b** | 4.7 GB | 8 GB | Balanced chat |
| **mistral:7b** | 4.1 GB | 6 GB | Fast, accurate chat |
| **phi3:mini** | 2.3 GB | 3 GB | Lightweight, fast |

### For Specialized Tasks

| Model | Size | RAM | Best For |
|-------|------|-----|----------|
| **llava:7b** | 4.7 GB | 6 GB | Vision + language (image analysis) |
| **mixtral:8x7b** | 26 GB | 32 GB | High performance MoE |
| **gemma2:9b** | 5.4 GB | 8 GB | Google efficient model |
| **qwen2.5-coder:7b** | 4.4 GB | 6 GB | Multilingual coding |

### For Low-Resource Servers (4-8 GB RAM)

| Model | Size | RAM | Best For |
|-------|------|-----|----------|
| **llama3.2:1b** | 1.3 GB | 2 GB | Ultra-lightweight |
| **phi3:mini** | 2.3 GB | 3 GB | Efficient chat |
| **tinyllama:1b** | 637 MB | 1.5 GB | Minimal resources |
| **gemma:2b** | 1.4 GB | 2.5 GB | Google small model |

**Recommendation:** Start with pre-installed models, then experiment based on your needs.

## Model Performance

### Inference Speed

Factors affecting speed:
- **Model Size:** Larger = slower
- **CPU Cores:** More cores = faster
- **RAM Speed:** DDR4-2666+ recommended
- **AVX Support:** CPU feature that accelerates inference

Check CPU features:
```bash
lscpu | grep -i avx
```

**Typical Inference Times (on 4-core CPU):**
- 3B model: 10-30 tokens/second
- 7B model: 5-15 tokens/second
- 13B model: 2-8 tokens/second

### Memory Usage

Models consume RAM while loaded:
- **Idle:** Minimal (model in memory)
- **Inference:** Model size + 1-2 GB overhead

**Example with 16 GB RAM:**
- System: 2 GB
- Docker/Services: 2 GB
- Available for AI: 12 GB
- Can run: Two 7B models OR One 13B model

Control loaded models:
```bash
# In .env:
OLLAMA_MAX_LOADED_MODELS=1  # Only keep 1 model in RAM
```

## Advanced Usage

### Custom Model Parameters

Create a Modelfile to customize behavior:

```bash
# Create Modelfile
cat > ~/coding-assistant-modelfile <<'EOF'
FROM deepseek-coder:6.7b

# Set temperature (creativity)
PARAMETER temperature 0.7

# Set context window
PARAMETER num_ctx 4096

# Custom system prompt
SYSTEM You are a helpful coding assistant focused on clean, efficient code.
EOF

# Create custom model
docker cp ~/coding-assistant-modelfile ollama:/tmp/
docker exec ollama ollama create coding-assistant -f /tmp/coding-assistant-modelfile
```

### Run Models with Custom Parameters

```bash
# Via API
curl http://localhost:11434/api/generate -d '{
  "model": "deepseek-coder:6.7b",
  "prompt": "Write a Python function for fibonacci",
  "options": {
    "temperature": 0.7,
    "top_p": 0.9,
    "num_predict": 500
  },
  "stream": false
}'
```

### Multi-Model Strategy

For 16 GB+ RAM servers, run multiple models:

```bash
# In .env:
OLLAMA_MAX_LOADED_MODELS=2
OLLAMA_NUM_PARALLEL=2

# Load models
docker exec ollama ollama pull deepseek-coder:6.7b
docker exec ollama ollama pull llama3.2:3b

# Both stay in memory for quick switching
```

## Integration with n8n

### Ollama Node in n8n

1. Add "Ollama" node to workflow
2. Configure:
   - Host: `http://ollama:11434`
   - Model: `deepseek-coder:6.7b` or `llama3.2:3b`
3. Use for:
   - Code generation
   - Text analysis
   - Automated responses
   - Data processing

### Example Workflow Ideas

**GitHub Webhook → Ollama → Slack:**
1. Receive PR webhook from GitHub
2. Send code to Ollama for review
3. Post AI review to Slack

**Email → Ollama → Response:**
1. Receive email via IMAP
2. Generate response with Ollama
3. Send via SMTP

## Troubleshooting

### Model Download Fails

```bash
# Check disk space
df -h ./data/ollama

# Check internet connection
curl -I https://ollama.ai

# Manual download with longer timeout
docker exec ollama sh -c "OLLAMA_TIMEOUT=3600 ollama pull model-name"

# Check logs
docker compose logs ollama
```

### Out of Memory During Inference

```bash
# Use smaller model
docker exec ollama ollama pull llama3.2:1b

# Reduce loaded models
# In .env: OLLAMA_MAX_LOADED_MODELS=1
docker compose up -d --force-recreate ollama

# Add swap
sudo fallocate -l 8G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Slow Inference

```bash
# Check CPU usage
top

# Reduce parallel requests
# In .env: OLLAMA_NUM_PARALLEL=1

# Use quantized models (already default)
# Check model info
docker exec ollama ollama show model-name

# Try smaller model
docker exec ollama ollama pull phi3:mini
```

### Model Not Loading

```bash
# Check model exists
docker exec ollama ollama list

# Try loading manually
docker exec ollama ollama run model-name "test prompt"

# Check Ollama logs
docker compose logs ollama | tail -50

# Restart Ollama
docker compose restart ollama
```

## Best Practices

### Resource Management

1. **Start small:** Use 3B-7B models first
2. **Monitor usage:** Check `docker stats` regularly
3. **Unload unused models:** Remove models you don't use
4. **Control parallelism:** Set `OLLAMA_NUM_PARALLEL` based on RAM

### Model Selection

1. **Test before committing:** Download, test, keep or remove
2. **Match to task:** Coding models for code, chat models for chat
3. **Consider quantization:** 4-bit models offer best balance
4. **Read model cards:** Check https://ollama.ai/library for details

### Performance Optimization

1. **Enable AVX:** Check CPU supports it
2. **Use SSD:** Fast storage improves model loading
3. **Increase timeout:** For large models: `OLLAMA_LOAD_TIMEOUT=1200`
4. **Batch requests:** Process multiple requests together

## Model Update Strategy

Models improve over time. Update periodically:

```bash
# Check for updates
# Visit: https://ollama.ai/library

# Update model (downloads new version)
docker exec ollama ollama pull deepseek-coder:6.7b

# Compare versions
docker exec ollama ollama show deepseek-coder:6.7b

# Remove old version if needed
docker exec ollama ollama rm old-model-name
```

## Resources

- **Model Library:** https://ollama.ai/library
- **Model Cards:** Read details, capabilities, limitations
- **Ollama Documentation:** https://github.com/ollama/ollama/tree/main/docs
- **Community Models:** https://ollama.ai/search

## Monitoring Model Usage

Track model performance:

```bash
# Check running models
docker exec ollama ollama ps

# Monitor resource usage
docker stats ollama

# Check Ollama logs
docker compose logs -f ollama

# API health check
curl http://localhost:11434/api/version
```

For detailed monitoring, see [MONITORING_DEPLOYMENT.md](MONITORING_DEPLOYMENT.md).
