# Local Model Setup (Ollama)

This project supports running all agents against locally-hosted LLMs via
[Ollama](https://ollama.com) — no API keys or cloud costs required.

## Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## Start the server

```bash
ollama serve
```

## Pull a model

```bash
# Recommended starting point (4.7 GB)
ollama pull llama3.1:8b

# Or pull everything in the catalog
bash models/setup_models.sh all

# Pull only DeepSeek models
bash models/setup_models.sh deepseek
```

## Select a model

Set these in your `.env` file:

```env
LLM_PROVIDER=ollama
LOCAL_MODEL=llama3.1:8b      # any model ID from models.yaml
OLLAMA_BASE_URL=http://localhost:11434
```

## Optional: custom finance-tuned model

```bash
# Llama variant
ollama create buyside-llama -f models/Modelfile.llama

# DeepSeek variant
ollama create buyside-deepseek -f models/Modelfile.deepseek
```

Then set `LOCAL_MODEL=buyside-llama` (or `buyside-deepseek`) in `.env`.

## Model catalog

See [models.yaml](models.yaml) for the full list of supported models with sizes.

| Model | ID | Size |
|---|---|---|
| Llama 3.1 8B ✓ | `llama3.1:8b` | 4.7 GB |
| Llama 3.3 70B | `llama3.3:70b` | 43 GB |
| Llama 3.2 3B | `llama3.2:3b` | 2.0 GB |
| DeepSeek R1 7B | `deepseek-r1:7b` | 4.7 GB |
| DeepSeek R1 14B | `deepseek-r1:14b` | 9.0 GB |
| DeepSeek R1 32B | `deepseek-r1:32b` | 20 GB |

✓ = recommended default
