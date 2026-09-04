# OpenMS module consolidation pattern

When multiple Snakemake modules share identical conda dependencies (e.g. all
OpenMS-based modules needing `openms=3.1.0` + `openms-thirdparty=3.1.0`),
consolidate them into a single SIF under a shared parent directory.

## Before (8 separate SIFs)

```
modules/
  raw2mzml/raw2mzml.{smk,json,yaml,def}
  decoydatabase/decoydatabase.{smk,json,yaml,def}
  searchengine/searchengine.{smk,json,yaml,def}
  psmrescoring/psmrescoring.{smk,json,yaml,def}
  psmfdr/psmfdr.{smk,json,yaml,def}
  proteininference/proteininference.{smk,json,yaml,def}
  quantification/quantification.{smk,json,yaml,def}
  msstats/msstats.{smk,json,yaml,def}
```

Each module had its own `.yaml` and `.def` (identical content), and its own
`.sif` in `Database/env/<name>/`. The config `env` section had 8 entries.

## After (1 shared SIF)

```
modules/openms/
  openms.yaml          # shared env definition
  openms.def           # generated from openms.yaml via EnvUtil
  raw2mzml/raw2mzml.{smk,json}
  decoydatabase/decoydatabase.{smk,json}
  searchengine/searchengine.{smk,json}
  psmrescoring/psmrescoring.{smk,json}
  psmfdr/psmfdr.{smk,json}
  proteininference/proteininference.{smk,json}
  quantification/quantification.{smk,json}
  msstats/msstats.{smk,json}
```

Single SIF: `Database/env/openms/openms.sif`. Config `env` section has one entry:
```json
"env": {
    "env_dir": "/home/luosg/Database/env",
    "openms": "/home/luosg/Database/env/openms/openms.sif"
}
```

## Migration steps

1. Create `modules/openms/` directory.
2. Move each module's `.smk` and `.json` into `modules/openms/<name>/`.
3. Create shared `modules/openms/openms.yaml` with all dependencies.
4. Update each `.smk` file:
   - `conda: "<name>.yaml"` → `conda: "../openms.yaml"`
   - `sif("<name>.yaml")` → `sif("openms.yaml")`
   - `include: "../common/common.smk"` → `include: "../../common/common.smk"`
   - Use `replace_all=True` since the yaml string appears in both `conda:` and `container:` lines.
5. Update `subworkflow/<Workflow>.smk` module imports:
   - `snakefile: "../modules/<name>/<name>.smk"` → `snakefile: "../modules/openms/<name>/<name>.smk"`
6. Update config `env` section: replace N entries with one `openms` entry.
7. Update runtime config (`raw.json`) with same env change.
8. Generate `openms.def` via `EnvUtil` or manually (ensure canonical `%post` template).
9. Build: `apptainer build --force --fakeroot openms.sif openms.def`
10. Remove old module directories and old env directories after verification.

## Pitfalls

- **Don't flatten subdirectories.** Each module keeps its own `<name>/` subdir
  under `modules/openms/` — the `.smk` files have unique rule logic.
- **`sif("openms.yaml")` resolves via `config["env"]["openms"]`.** The yaml
  filename stem must match the config key. If using a different name, update
  both the yaml stem and the config key.
- **`conda:` directive path is relative to the snakefile.** Since smk files are
  in `modules/openms/<name>/`, the shared yaml at `modules/openms/openms.yaml`
  requires `../openms.yaml`.
- **`include:` relative paths break.** Each `.smk` has `include: "../common/common.smk"`.
  After moving from `modules/<name>/` to `modules/openms/<name>/`, this becomes
  one level deeper. Update to `include: "../../common/common.smk"` in ALL moved
  `.smk` files. Snakemake does not give a clear error — it just can't find the
  include file.
- **Old env dirs can be removed** after verifying the new SIF works. Keep the
  old dirs during migration to allow rollback.
