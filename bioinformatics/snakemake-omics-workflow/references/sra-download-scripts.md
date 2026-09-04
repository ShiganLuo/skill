# SRA Data Download Scripts

Location: `src/download/`

## Architecture

`sra_download.py` supports two download methods via `-m/--method`:

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

## Aspera key issues

The aspera-cli 3.9.6 bundled DSA key (`asperaweb_id_dsa.openssh`) may fail with EBI ENA:
- Symptom: `ascp: failed to authenticate, exiting.`
- Root cause: EBI updated Aspera server authentication
- Port 33001 may be open (ping works) but auth fails
- Workaround: use `-m sra` instead

## Pitfall: stderr capture

Always use `capture_output=True, text=True` in `subprocess.run()` and log `result.stderr` on failure. Never use `stderr=subprocess.DEVNULL` — it hides actionable error messages. See skill pitfall #34.
