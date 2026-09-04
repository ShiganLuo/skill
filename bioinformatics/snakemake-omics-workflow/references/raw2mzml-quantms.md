# Proteomics raw-to-mzML + QuantMS notes

Session learning:
- The existing QuantMS subworkflow is mzML-centric; it should not be asked to ingest Thermo `.raw` directly.
- Add a dedicated raw-to-mzML module before QuantMS when users provide `.raw` inputs.
- Keep `runQuantMS()` focused on declaring `raw_files`, `mzml_files`, and `outfiles`; the raw conversion step owns the file-format bridge.
- Accept a raw manifest keyed by `sample_id` when source paths are not implied by filename.

Implementation shape used in this session:
- `modules/openms/raw2mzml/raw2mzml.smk`
- `modules/openms/raw2mzml/raw2mzml.yaml`
- `subworkflow/QuantMS.smk` wires `raw2mzml` ahead of search/quantification rules
- `node.py` emits `raw_files` and `raw2mzml_dir` into the instance JSON when raw input is enabled

Practical caveats:
- `.raw` is archival; `mzML` is the standard analysis input.
- Keep file naming deterministic: `raw2mzml/{sample_id}/{sample_id}.mzML`.
- When adding this bridge, verify the instance JSON and the derived output paths with a temporary script before declaring success.
