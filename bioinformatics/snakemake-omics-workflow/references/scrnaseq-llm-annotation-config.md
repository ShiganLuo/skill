# scRNAseq LLM Annotation Config Flow

## Config chain

```
config/scRNAseq.json  →  node.runscRNAseq()  →  raw.json  →  scanpy.smk  →  scRNAseq.py
```

## Fields (under `Params.<counter>.annotate`)

| Field | Default | Description |
|-------|---------|-------------|
| `llm_method` | `""` | `"openai"`, `"ollama"`, `"file"` (empty = skip LLM) |
| `llm_model` | `"gpt-4o"` | Model identifier |
| `llm_api_key` | `""` | API key for OpenAI-compatible backends |
| `llm_base_url` | `""` | Base URL for API endpoint |
| `llm_top_genes` | `30` | Number of top DEGs per cluster to send in prompt |
| `annotate_group` | `"leiden"` | Column in `adata.obs` for cluster membership |

## Environment variable injection (node.py)

In `runscRNAseq()`, after counter validation and before writing raw.json, LLM fields are injected from env vars as fallback (config takes priority):

```python
env_llm_model = os.environ.get("LLM_MODEL", "")
env_llm_api_key = os.environ.get("LLM_API_KEY", "")
env_llm_base_url = os.environ.get("LLM_BASE_URL", "")
for counter in counters:
    annotate = datajson["Params"].setdefault(counter, {}).setdefault("annotate", {})
    if env_llm_model and not annotate.get("llm_model"):
        annotate["llm_model"] = env_llm_model
    if env_llm_api_key and not annotate.get("llm_api_key"):
        annotate["llm_api_key"] = env_llm_api_key
    if env_llm_base_url and not annotate.get("llm_base_url"):
        annotate["llm_base_url"] = env_llm_base_url
```

Priority: config value > environment variable > empty string.

## Snakemake param resolution (scanpy.smk)

```python
llm_model=lambda wildcards: params.get(wildcards.counter, {}).get("annotate", {}).get("llm_model", ""),
llm_api_key=lambda wildcards: params.get(wildcards.counter, {}).get("annotate", {}).get("llm_api_key", ""),
llm_base_url=lambda wildcards: params.get(wildcards.counter, {}).get("annotate", {}).get("llm_base_url", ""),
```

## Python CLI arg passing (scanpy.smk run block)

Only passed to CLI if non-empty:
```python
if params.llm_model:
    cmd += ["--llm-model", params.llm_model]
if params.llm_api_key:
    cmd += ["--llm-api-key", params.llm_api_key]
if params.llm_base_url:
    cmd += ["--llm-base-url", params.llm_base_url]
```

## Counters

Both `scTE` and `cellranger` counters get their own `annotate` section in the config. The env var injection iterates over `datajson["counters"]` to populate all of them.
