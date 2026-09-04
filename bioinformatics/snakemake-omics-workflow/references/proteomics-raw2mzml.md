# Proteomics raw2mzML integration notes

Use this pattern when adding vendor `.raw` ingestion to QuantMS-style workflows.

## Recommended contract
- `sample_id`: workflow sample key
- `raw_path`: absolute path to vendor `.raw`
- `organism`
- `assay_type`: `DIA` / `TMT` / `LFQ`
- optional `project_id`, `condition`, `replicate`, `batch`

## Flow
1. `run.py` selects `QuantMS`.
2. `node.runQuantMS()` loads a raw manifest when present.
3. `raw_files` and derived `mzml_files` are written into `raw.json`.
4. `subworkflow/QuantMS.smk` adds a thin `raw2mzml` module before decoy/search/quantification.
5. `modules/raw2mzml/raw2mzml.json` is a module config template, not workflow state.

## Module shape
- Keep `raw2mzml` atomic: one input family, one conversion step, one mzML output family.
- Use `ThermoRawFileParser` (bundled in openms.sif) — `msconvert` is not available via conda.
- Emit per-sample outputs under `outdir/raw2mzml/{sample_id}/{sample_id}.mzML`.
- As of 2026-08, all 8 OpenMS modules (including raw2mzml) are consolidated under `modules/openms/` sharing a single `openms.sif`. See `references/openms-module-consolidation.md`.

## Container pitfalls (raw2mzml.sif)

**`openms-thirdparty` does NOT include `msconvert`.** The package ships a `.ttd` wrapper (`share/OpenMS/TOOLS/EXTERNAL/msconvert.ttd`) that expects `msconvert` to already be in `$PATH`, but the ProteoWizard binary itself is NOT bundled. Building a container with only `openms-thirdparty=3.1.0` will produce a SIF where `msconvert` → `command not found`.

What `openms-thirdparty` DOES provide in the bin: `ThermoRawFileParser`, `FileConverter`, and other OpenMS CLI tools — but not `msconvert`.

**Fix options:**
1. Add `proteowizard` to the conda YAML (`raw2mzml.yaml`) and rebuild the SIF. Check availability in bioconda first — ProteoWizard has licensing restrictions and may not be conda-installable.
2. Switch to `ThermoRawFileParser` (already in the container). See ThermoRawFileParser section below.
3. Use OpenMS `FileConverter` for `.raw` → `.mzML` conversion.

**Diagnostic when debugging:** `singularity exec <sif> bash -c 'echo $PATH; ls /opt/conda/envs/<env>/bin/ | grep -i msconvert'` — if empty, msconvert is missing from the image.

## ThermoRawFileParser as msconvert replacement

CLI syntax:
```bash
ThermoRawFileParser -i input.raw -b output.mzML -f 1
# -i: input raw file
# -b: exact output file path (or -o for output directory)
# -f: format — 0=MGF, 1=mzML, 2=indexed mzML, 3=Parquet
```

**Peak picking is ON by default.** The `-p` / `--noPeakPicking` flag DISABLES it (opposite of msconvert's `--filter 'peakPicking true 1-'`). When `peak_picking=True` in config, omit `-p`; when `False`, add `-p`.

Config change pattern (3 files: `config/<Workflow>.json`, `modules/raw2mzml/raw2mzml.json`, runtime `raw.json`):
```json
"raw_to_mzml": {
    "mode": "thermorawfileparser",
    "converter": "ThermoRawFileParser",
    "peak_picking": true
}
```

Rule `run:` block — add an `elif` branch:
```python
elif params.converter_mode == "thermorawfileparser":
    cmd.extend(["-i", str(input.infile), "-b", str(output.mzml), "-f", "1"])
    if not params.peak_picking:
        cmd.append("-p")
```

## Symlink resolution + singularity bind mounts

Vendor `.raw` files are often symlinks (e.g. created by manifest/ingestion scripts). Inside singularity with `--home <dir>`, only paths under `<dir>` are accessible. Symlinks pointing outside break silently — ThermoRawFileParser reports `Unable to access the RAW file using the native Thermo library` (not a clear symlink error).

**Fix (two parts):**

1. **Resolve symlinks in `get_raw_input()`** — use `os.path.realpath()`:
```python
def get_raw_input(wildcards):
    ...
    for path in candidates:
        if os.path.exists(path):
            return os.path.realpath(path)  # was: return path
```

2. **Ensure resolved paths are bind-mounted** — `run.py`'s `_collect_bind_paths()` scans the config JSON for paths. Add `raw_files` with resolved (non-symlink) paths to the runtime config (`raw.json`):
```json
"raw_files": [
    "/real/path/to/sample1.raw",
    "/real/path/to/sample2.raw"
]
```
For `run.py` runs, update `node.runQuantMS()` to populate `raw_files` with `os.path.realpath()` resolved paths. For manual snakemake runs, pass `--singularity-args '--bind /real/data/dir,...'`.

**Diagnostic:** `file <path>` — if it says `symbolic link to ...`, the target is what needs bind-mounting. `realpath <path>` gives the actual path.

## Verification pattern
When no canonical test target exists, use a temporary script under `/tmp` with prefix `hermes-verify-` and assert:
- manifest parsing
- derived mzML output path
- `runQuantMS()` payload contains `samples`, `raw_files`, `mzml_files`, `outfiles`
- temp script exits 0 and is deleted after use
