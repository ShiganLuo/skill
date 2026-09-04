# No Silent Fallback Convention

## Rule

Never write fallback code paths that silently change behavior when the expected state is missing. If a column, file, or configuration value doesn't exist, the code should **fail loudly** — not quietly fall back to a default or skip the step.

## Example

```python
# WRONG — silent fallback hides bugs
hvg_batch = "sample_id" if "sample_id" in adata.obs.columns else "sample"
hvg_batch = hvg_batch if hvg_batch in adata.obs.columns else None  # silently disables batching

# CORRECT — fail fast with clear error
sc.pp.highly_variable_genes(adata, batch_key="sample_id")  # KeyError if missing = good
```

## Why

Silent fallbacks mask data pipeline bugs. A missing column usually means upstream logic is wrong — falling back to `None` or a different column produces silently wrong results that are harder to debug than a crash.

User explicitly stated: "不要做fallback, fallback比报错还危险" (don't use fallback, fallback is more dangerous than an error).

## Exception

Fallback is acceptable when:
- The user explicitly asks for it
- It's a display-only choice (e.g., fallback from `sample_id` to `sample` column for a plot title)

Never use fallback for data processing logic.

## Related Pitfalls

- aria2c download with `--continue=true` + server-side file corruption = infinite retry loop. The `spin_until_success` pattern retries the same bad data forever. When `gzip -t` fails on a file whose size matches HTTP `Content-Length`, the source is corrupted — retry won't help. Switch download source (NCBI SRA prefetch instead of ENA HTTP).
