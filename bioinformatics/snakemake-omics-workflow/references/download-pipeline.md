# Download Pipeline: GSE → Downstream Files

## Overview

`src/download/GSE_runinfo.py` has `fetch_gse_files(gse_id, outdir)` that takes a GSE ID and produces all files needed by downstream branches:

- `gsm_metadata.csv` — GSM-level metadata (Characteristics, GSE, SRA, BioSample)
- `sra_metadata.csv` — SRA-level metadata (library info, SRR runs)
- `meta_input.tsv` — combined metadata (sample_id, data_id, fastq_1, fastq_2, design)

## Pipeline Steps

1. **Query NCBI**: `_get_gsm_ids_from_gse(gse_id, email)` uses Entrez esearch on GDS database to find ALL related UIDs (GSE + GPL + GSM), then esummary to get accessions, filtering for GSM. Do NOT use elink — it returns empty results for GDS→GDS links.

2. **Download GSM metadata**: `GSM_metadata.download_batch()` fetches GSM XML/HTML pages, then `extract_gsm_batch()` parses Characteristics, GSE, SRA, BioSample IDs.

3. **Download SRA metadata**: `GSM_metadata.download_batch()` fetches SRX HTML pages, then `extract_sra_batch()` parses library info and SRR runs.

4. **Generate meta_input.tsv**: `generate_meta_input.generate_meta_input()` merges gsm_metadata + sra_metadata + fastq_dir → meta_input.tsv.

## Usage

### Python API
```python
from src.download.GSE_runinfo import fetch_gse_files

result = fetch_gse_files(
    gse_id="GSE12345",
    outdir="/path/to/output",
    email="your@email.com",
    workers=4,
)
# result.gsm_metadata_csv, result.sra_metadata_csv, result.meta_input_tsv
```

### CLI
```bash
python GSE_runinfo.py -i gse_ids.txt -o /path/to/output -m gse_pipeline --email your@email.com
```

## Pitfalls

1. **Lazy imports for sibling modules**: Use `importlib.import_module()` to avoid circular dependencies when importing GSM_metadata or generate_meta_input from GSE_runinfo.py.

2. **@dataclass from dataclasses, not typing**: Import `@dataclass` from `dataclasses` module, not from `typing`.

3. **GSM metadata uses esummary, NOT efetch**: `Entrez.efetch(db="gds", rettype="xml")` returns plain text, NOT XML. Use `Entrez.esummary(db="gds", id=uid)` to get structured data, then build XML manually. For SRA/BioSample accessions, use requests to download HTML.

4. **SRA metadata requires SRX HTML pages**: `extract_sra_batch()` expects SRX*.html files in the html_dir. These are downloaded from SRA (not GEO).

5. **meta_input.tsv requires both gsm_metadata.csv and sra_metadata.csv**: If either is missing, meta_input.tsv cannot be generated.

6. **BioPython Entrez + SOCKS5 proxy**: BioPython's Entrez uses urllib internally, which does NOT natively support SOCKS5 proxies. Must do TWO things:
   a) Monkey-patch socket via PySocks (so TCP connections go through SOCKS5)
   b) Clear proxy env vars (because urllib reads them and fails on the `socks5://` URL scheme it doesn't understand)
   ```python
   import socks, socket, os
   # Parse proxy from env
   proxy_url = os.environ.get('all_proxy', '')
   m = re.match(r'socks[45]h?://([^:]+):(\d+)', proxy_url)
   host, port = m.group(1), int(m.group(2))
   # Clear proxy env vars (urllib can't parse socks5://)
   saved = {k: os.environ.pop(k, None) for k in ['all_proxy','http_proxy','https_proxy','ALL_PROXY','HTTP_PROXY','HTTPS_PROXY']}
   # Monkey-patch socket
   orig = socket.socket
   socks.set_default_proxy(socks.SOCKS5, host, port)
   socket.socket = socks.socksocket
   try:
       # Entrez calls here
   finally:
       socket.socket = orig
       for k, v in saved.items():
           if v is not None: os.environ[k] = v
   ```
   `GSM_metadata.py` (requests-based) handles SOCKS5 natively via PySocks — no patching needed there.

7. **esearch default retmax=20**: `Entrez.esearch(db="gds")` returns only20 UIDs by default. Must set `retmax=total_count` to get all results. Pattern: first call with `retmax=1` to get Count, then second call with `retmax=Count`.

8. **esummary returns IntegerElement**: `Entrez.esummary` returns `IntegerElement` objects for numeric fields (e.g., n_samples), not plain integers. Convert with `int(value)` or check `hasattr(value, 'attributes')`.

9. **GSE field needs prefix**: esummary returns GSE as just the number (e.g., "36552"), not "GSE36552". Always prepend "GSE" if not already present.

10. **GSM records have n_samples=0**: For GSM (single sample) records, n_samples is always 0 and meaningless. Exclude this field from GSM output.

11. **Preserve GSM order**: Use `list(dict.fromkeys(gsm_ids))` for deduplication instead of `sorted(set(gsm_ids))` to preserve the order from esearch results.

## File Structure

```
outdir/
├── html/                    # Downloaded HTML/XML pages
│   ├── GSM*.xml            # GSM metadata (Entrez XML)
│   ├── SRX*.html           # SRA experiment pages
├── gsm_metadata.csv        # GSM-level metadata
├── sra_metadata.csv        # SRA-level metadata
├── meta_input.tsv          # Combined metadata for Snakemake
└── fastq/                  # FASTQ files (downloaded separately)
```

## Related Files

- `src/download/GSM_metadata.py` — GSM/SRA metadata download and extraction
- `src/download/generate_meta_input.py` — meta_input.tsv generation
- `src/download/sra_download.py` — FASTQ file download (not included in fetch_gse_files)
- `src/download/AccessionResolver.py` — accession ID classification