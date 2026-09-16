---
name: ngs-data-download
description: Download NGS raw data (fastq/SRA) from public repositories - ENA, SRA/NCBI, Globus. Covers download methods, speed optimization, and troubleshooting broken Aspera authentication.
tags: [bioinformatics, ngs, download, sra, ena, aspera, aria2c, prefetch, globus]
triggers:
  - User needs to download fastq or SRA files from ENA, NCBI SRA, or GEO
  - User needs GEO metadata (GSM characteristics, GSE series info, SRA/BioSample cross-refs)
  - User mentions Entrez, esearch, efetch, elink, or Biopython for NCBI data
  - User mentions Globus, Aspera, ascp, enaDataGet, or prefetch
  - User complains about slow download from sequence repositories
  - User asks about ENA Aspera authentication failures
---

# NGS Raw Data Download

Download fastq/SRA files from public sequence repositories (ENA, NCBI SRA, GEO).

## Repository Overview

| Repository | URL | Data Format | Download Methods |
|-----------|-----|-------------|-----------------|
| ENA (EBI) | ftp.sra.ebi.ac.uk/vol1/ | fastq.gz, sra | HTTP, FTP, Aspera (broken), Globus |
| NCBI SRA | ncbi.nlm.nih.gov/sra | sra | prefetch (HTTP/fasp), Globus |
| GEO (metadata) | Entrez API (GDS db) | XML | Biopython Entrez |
| GEO (suppl. files) | ncbi.nlm.nih.gov/geo | supplementary files | wget, curl |

## Method 0: Entrez API for GEO Metadata (Recommended for GSM/GSE/GPL metadata)

GEO web pages block plain `requests` — use NCBI's Entrez API (Biopython) instead.
Fetches structured XML with GSE IDs, SRA/BioSample cross-references via `esearch` + `efetch` + `elink`.

⚠️ Characteristics key-value pairs are NOT in Entrez XML — only GSE/SRA/BioSample IDs and basic metadata.

See `references/entrez-geo-metadata.md` for full workflow, XML parsing patterns, and rate limits.

## Method 1: aria2c Multi-Thread HTTP (Recommended for ENA fastq)

Best speed-to-simplicity ratio. Downloads directly from ENA's HTTP server with parallel connections.

```bash
# Single file
aria2c -x 8 -s 8 -k 1M "http://ftp.sra.ebi.ac.uk/vol1/fastq/ERR164/ERR164407/ERR164407.fastq.gz"

# Batch: feed a file list (one URL per line)
aria2c -x 8 -s 8 -k 1M -j 4 -i url_list.txt
# -x 8: 8 connections per file
# -s 8: split into 8 segments
# -k 1M: min segment size 1MB
# -j 4: 4 concurrent downloads (for batch)
```

ENA URL pattern for fastq:
```
http://ftp.sra.ebi.ac.uk/vol1/fastq/<accession_prefix_6>/<accession>/<accession>_1.fastq.gz
http://ftp.sra.ebi.ac.uk/vol1/fastq/<accession_prefix_6>/<accession>/<accession>_2.fastq.gz
```
Where `<accession_prefix_6>` = first 6 chars of accession (e.g. ERR164 from ERR164407).

For accessions longer than 9 digits, a zero-padded subdirectory is added:
```
# ERR164407 (9 chars): vol1/fastq/ERR164/ERR164407/
# ERR6090701 (10 chars): vol1/fastq/ERR609/001/ERR6090701/       # "00" + last 1 digit
# SRR12345678 (11 chars): vol1/fastq/SRR123/078/SRR12345678/    # "0" + last 2 digits
```

To get URLs programmatically, use ENA Portal API:
```bash
curl "https://www.ebi.ac.uk/ena/portal/api/filereport?accession=PRJEBXXXX&result=read_run&fields=run_accession,fastq_ftp,fastq_md5&format=tsv"
```

## Method 2: prefetch + fasterq-dump (Recommended for SRA .sra files)

NCBI SRA Toolkit. Downloads .sra format then converts to fastq.

```bash
# Download .sra file via HTTP
prefetch -t http ERR164407 -O /output/dir

# Convert to fastq
fasterq-dump --split-3 /output/dir/ERR164407/ERR164407.sra -O /output/dir

# Compress output
gzip /output/dir/ERR164407*.fastq
```

- `-t http`: Use HTTPS transport (fasp/Aspera transport is broken, see below)
- `-O`: output directory
- `--split-3`: split paired-end reads into _1.fastq and _2.fastq

## Method 3: Globus (Large batch, institutional)

Globus is reliable for very large transfers but can be slow due to:
- Endpoint bandwidth limits (source or destination)
- Relay routing when endpoints can't connect directly
- Globus Connect Personal (GCP) throttling
- International bandwidth (especially China -> EBI/NCBI)

Speed optimization: increase pipelining and parallelism in transfer settings.

## ENA Aspera Status: BROKEN (as of 2026-08)

ENA's Aspera (ascp) authentication no longer works. Root cause identified via `ascp -L-` verbose logging:

```
[libssh2] Unable to exchange encryption keys
ERR [asssh] SSH connection startup failed, err = -5
ERR [ascp] SSH connection startup encountered invalid protocol
```

This is **SSH protocol incompatibility**, not just a key issue. ascp 3.9.1 (2022) cannot complete the SSH key exchange with ENA's current server. All key files tested and rejected:
- `asperaweb_id_dsa.openssh` - FAILS (SSH handshake fails before auth)
- `aspera_tokenauth_id_rsa` - FAILS (same)
- ascli built-in bypass keys (embedded in gem `lib/aspera/data/`) - FAILS (same)
- NCBI prefetch `-t fasp` - FAILS ("cannot download using requested transport")

The IBM SDK download URL (`ibm.biz/sdk_location`) is blocked from China, so ascli cannot auto-download a newer ascp to fix the protocol mismatch.

**Do NOT waste time trying to fix Aspera for ENA downloads.** Use aria2c HTTP or prefetch -t http instead.

### ascli Dependency Fix (if needed for non-ENA Aspera)

ascli 4.20.0 in conda env `DNA` (Ruby 3.4) has a broken dependency chain. Fix order:
1. `gem install webrick` — Ruby 3.4 removed webrick from default gems
2. Symlink `x86_64-conda-linux-gnu-cc` -> `/usr/bin/gcc` in env's `bin/` — conda Ruby's mkmf hardcodes the conda cross-compiler name which isn't installed
3. `gem install bigdecimal` — Ruby 3.4 removed bigdecimal from default gems; coercible -> symmetric_encryption -> aspera-cli chain breaks without it
4. Set `GEM_PATH=/home/luosg/miniconda3/envs/DNA/share/rubygems` so rubygems finds the installed gems
5. Symlink ascp to `~/.aspera/sdk/ascp` so ascli can find the transfer binary

See `references/ena-aspera-troubleshooting.md` for detailed test results, ascli fix chain, and bypass key extraction.

## Post-Download: Design Generation

After downloading fastq files, generate `meta_input.tsv` (including the `design` column) in a single step using `generate_meta_input.py`:

```bash
python generate_meta_input.py \
    -g gsm_metadata.csv \
    -i sra_metadata.csv \
    -d fastq/ \
    -o meta_input.tsv
```

Single unified function — no subcommands. The `design` column is auto-built from **all non-identifier columns** in `gsm_metadata.csv` (excluding `GSM`, `GSE`, `SRA`, `BioSample`). Non-empty values are joined with `_` to form the group name, then `.repN` is assigned within each group by GSM occurrence order. Technical replicates (same GSM, multiple SRRs) share the same rep number. See `references/generate-design.md` for full details.

## Method Selection Guide

| Scenario | Best Method | Typical Speed |
|----------|-------------|---------------|
| Few fastq.gz from ENA | aria2c -x 8 HTTP | ~8 MB/s |
| Batch fastq from ENA | aria2c -j 4 -x 8 HTTP + URL list | ~8 MB/s per file |
| SRA .sra files | prefetch -t http | ~9 MB/s |
| Very large batch (>TB) | Globus (if endpoint available) | variable |
| China network to EBI/NCBI | aria2c or prefetch -t http | ~6-9 MB/s |

## Pitfalls

- **GEO web pages block requests**: `requests.get()` on `geo/query/acc.cgi` returns empty/blocked responses. Use Entrez API (Biopython) for GEO metadata. See Method 0.
- **ENA Aspera is broken**: Root cause is SSH protocol incompatibility (ascp 3.9.1 vs ENA's current server), not just key issues. Don't try ascp/ascli for ENA. Use HTTP methods.
- **aria2c boolean flags need `=` syntax**: Use `--continue=true`, NOT `--continue true` (aria2c treats bare `true` as a URI and fails with "Unrecognized URI or unsupported protocol").
- **prefetch -t both doesn't work**: Use `-t http` explicitly; `-t both` and `-t fasp` both fail.
- **prefetch -o is deprecated**: Use `-O` (output directory) not `-o` (output file).
- **ENA URL subdirectory pattern**: Accessions with >9 digits have zero-padded subdirectories in the FTP path. Get URLs from the Portal API to avoid manual path construction.
- **fasterq-dump needs .sra path**: Pass the full path to the .sra file, not the accession.
- **Verify integrity**: ENA provides .md5 files alongside data. Always verify after download.
- **aria2c dynamic speed logging**: To show download speed in logs, use `subprocess.Popen` (not `run`) with `--summary-interval=5 --console-log-level=warn`, then stream stdout line-by-line. Throttle logging to 1 line per 5s with `time.time()` delta. Parse progress lines by matching `[#` prefix + `DL:` substring. Output the final progress line on "Download Results" only if `time.time() - last_log_time >= 2.0` to avoid duplicate near the throttle boundary. See `references/aria2c-streaming-pattern.md` for a copy-paste implementation.
- **generate_meta_input is a single unified function**: No subcommands. Takes `-g gsm_metadata.csv -i sra_metadata.csv -d fastq/ -o output.tsv`. Design is auto-built from all non-ID columns (excludes GSM/GSE/SRA/BioSample). Don't add subcommand patterns.
- **Mixed XML/HTML in same directory**: Entrez saves `.xml`, requests saves `.html`. When scanning for GSM files, glob both patterns and deduplicate (prefer XML). Detect format by `filepath.endswith(".xml")` to dispatch to the right parser.
- **uv pip install for venvs without pip**: Some conda-based venvs don't have pip. Use `uv pip install --python <venv>/bin/python <package>` instead.
- **ascli bypass keys are embedded in the gem**: Found at `lib/aspera/data/` (files `1`=dsa, `2`=rsa). Extract via Ruby: `Aspera::DataRepository.instance.item(:dsa)`. But they won't help for ENA since the failure is SSH-level, not key-level.
- **ascli SDK download blocked in China**: `ibm.biz/sdk_location` is unreachable from CN networks, so `ascli conf ascp install` hangs indefinitely. Must manually point ascli to an existing ascp binary via `~/.aspera/sdk/ascp` symlink.
- **ENA files can be corrupted at source**: If `gzip -t` fails on a freshly downloaded file whose size matches the HTTP `Content-Length` exactly, the file is corrupted on the ENA server — retrying aria2c downloads the same bad data in an infinite loop (download 50GB → gzip -t fails → delete → retry → same result). Diagnose with: `curl -sI <url> | grep Content-Length` vs `ls -la <file>` (sizes match = server-side corruption). Fix: switch to NCBI SRA (`prefetch -t http` + `fasterq-dump`) which uses a different data source.
- **sra_download.py key patterns (now implemented)**: `spin_until_success` has `max_retries` (default 10, via `--max-retries`); returns bool. `download_spin` checks `_fastq_exists()` before downloading (skip if fastq present + gzip-valid). `main()` collects failed SRRs, writes `download_failed.txt` to outdir, and `sys.exit(1)` on any failure. `load_tasks` uses `dropna(subset=[srr_col])` only — NOT `dropna()` on both columns, which silently drops samples with missing `library_layout`.
- **TSV NaN column trap (meta_download.tsv)**: When a TSV has fields containing embedded quotes or newlines (e.g. `gsm_sample_data_processing`), pandas `read_csv(sep='\t')` can misparse rows, producing fewer fields than the header. This causes trailing columns (like `library_layout`) to become NaN for affected rows. If `load_tasks` then does `df[[srr, layout]].dropna()`, those samples are silently excluded. Fix: `dropna(subset=[srr_col])` only, and `fillna(default_layout)` on the layout column. Use `--default-layout SINGLE` arg to handle missing layout gracefully. Detect the issue: `awk -F'\t' '{print NR": "NF" fields"}' file.tsv` — rows with fewer fields than the header indicate embedded delimiter/quoting problems.
- **prefetch silently skips large files**: `prefetch` defaults to `--max-size 20G`. Files larger than 20GB are silently skipped — the command exits 0 but no `.sra` file is created. The error message is buried in stderr: `is larger than maximum allowed: skipped`. Always pass `--max-size 0` (no limit) when downloading large SRA files:
  ```python
  prefetch_cmd = ["prefetch", srr_id, "-O", str(dest), "--max-size", "0"]
  ```
  Without this, `sra_download.py`'s post-check (`if not sra_file.exists()`) reports a confusing ".sra file not found" error that looks like a network failure.
