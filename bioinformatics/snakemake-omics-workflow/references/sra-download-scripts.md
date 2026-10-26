# SRA Data Download Scripts

Location: `src/download/`

## Architecture

`sra_download.py` supports five download methods via `-m/--method`: `ascp` (ENA Aspera), `aria2c` (ENA HTTP multi-thread), `curl` (ENA HTTPS, supports socks proxy), `sra` (NCBI prefetch+fasterq-dump, default), `globus` (ENA endpoint).

### ascp (ENA Aspera)
- Uses `era-fasp@fasp.sra.ebi.ac.uk` with key file
- Port 33001, protocol FASP
- Requires `--key` argument (path to `asperaweb_id_dsa.openssh`)
- May fail with `ascp: failed to authenticate` if key is outdated (see below)

### sra (NCBI SRA Toolkit) — default
- Uses `prefetch` to download .sra files
- Uses `fasterq-dump --split-files` to convert to FASTQ
- Uses `gzip` to compress
- Cleans up .sra files after successful conversion
- No key file needed

## CLI

```bash
# SRA toolkit (default, no key needed)
python sra_download.py -m sra --meta sra_metadata.csv --outdir fastq/ --log download.log

# Aspera (requires key)
python sra_download.py -m ascp --meta sra_metadata.csv --outdir fastq/ \
    -k assests/asperaweb_id_dsa.openssh --log download.log

# Parallel (4 workers)
python sra_download.py -m sra --meta sra_metadata.csv --outdir fastq/ --log download.log --jobs 4
```

## Meta file format

CSV/TSV with header. Default columns: `SRR` (accession), `Layout` (PAIRED|SINGLE).
Override with `--srr-col-name` and `--lib-col-name`.

## Integration with run.sh

`run.sh` calls `GSM_metadata.py` first to build `sra_metadata.csv`, then calls `sra_download.py`.

## Pitfall: stderr capture

Always use `capture_output=True, text=True` in `subprocess.run()` and log `result.stderr` on failure. Never use `stderr=subprocess.DEVNULL` — it hides actionable error messages. See skill pitfall #34.

## Pitfall: `--log` is optional, defaults to stdout

`-l/--log` is not required. When omitted, logs go to stdout (never error out). Guard the path: `str(args.log)` on `None` opens a log file literally named `None`. Pass `log_file=str(args.log) if args.log else None` and `stream=sys.stdout` when no log file. `LogUtil.setup_logger` accepts `stream=` for the console handler.

## Pitfall: prefetch `--max-size` semantics (sra method, verified 2.9.6)

`--max-size` is the max single-file size in KB (exclusive), default `20G`. There is NO "0 = unlimited": `--max-size 0` fails at argument parsing with `param invalid ... Maximum requested file size is zero`. Use a large explicit limit as the no-limit stand-in:

```python
prefetch_cmd = ["prefetch", srr_id, "-O", str(dest), "--max-size", "1T"]
```

Files above the limit are silently skipped (exit 0, no `.sra` created; stderr says `is larger than maximum allowed: skipped`), surfacing later as the confusing ".sra file not found" post-check.

When a download retry loop fails identically on every attempt, first check whether the tool rejects the ARGUMENTS before any network I/O (run the command manually). "param invalid" is deterministic — fix the argument from `--help` semantics; retry loops only burn sleeps.

## Pitfall: prefetch TLS verify fails where curl succeeds

prefetch bundles its own TLS stack (mbedtls) + CA store; behind TLS-intercepting gateways it fails `X509 - Certificate verification failed` for hosts that `curl` (system CA store) reaches fine. Retrying cannot help — fall back to `-m curl` (ENA path, supports socks proxies; aria2c cannot use socks proxies). Reachability differs per host on the same network (`www.ncbi.nlm.nih.gov`, `www.ebi.ac.uk` API, `ftp.sra.ebi.ac.uk` data) — probe each with `curl -sI` before choosing a method.
