# KARRseq Porting Case Study

## Source
Standalone Snakemake workflow at `/data/pub/zhousha/20260207_Exome/workflow/KARRseq/`

## Workflow Summary
KARR-seq (Kethoxal-Assisted RNA-RNA interaction sequencing) detects RNA-RNA interactions via chimeric read analysis.

## Steps Ported
1. **SeqPrep merge** — Merge paired-end reads → new `modules/seqprep/`
2. **STAR align** — Align with chimeric output → reused star module pattern but custom rule in subworkflow (existing star.smk doesn't output Chimeric.out.sam)
3. **Chimeric to pairs** — Extract chimeric pairs using `src/get_STAR_reads.py` → new `modules/karrseq/` with `bin/`
4. **Remove duplicates** — Dedup using `src/remove_duplicates.py` → karrseq module
5. **Ligation processing** — Process ligation events → karrseq module

## Key Decisions

### Why not reuse star module directly
The existing `modules/star/star.smk` doesn't output `Chimeric.out.sam`. Adding that output would require modifying the existing module. Since the constraint was "no modifications to existing code", I embedded the STAR rule directly in the subworkflow with KARRseq-specific parameters.

### Standalone run script pattern
When `run.py` can't be modified (read-only constraint), create `run_KARRseq.py` at project root:
- Loads `config/KARRseq.json` template
- Accepts CLI args (samples, paths, tool executables)
- Generates `raw.json` in output dir
- Calls snakemake with `--configfile`

### Scripts moved to bin/
Original `src/` scripts (`get_STAR_reads.py`, `remove_duplicates.py`, `pairs_to_bed.py`) copied to `modules/karrseq/bin/` following the project convention.

## Files Created
```
config/KARRseq.json                          # Config template
modules/seqprep/seqprep.smk                  # SeqPrep merge rule
modules/seqprep/seqprep.json
modules/seqprep/seqprep.yaml
modules/karrseq/karrseq.smk                  # Chimeric processing rules
modules/karrseq/karrseq.json
modules/karrseq/karrseq.yaml
modules/karrseq/bin/get_STAR_reads.py        # From KARRseq src/
modules/karrseq/bin/remove_duplicates.py
modules/karrseq/bin/pairs_to_bed.py
subworkflow/KARRseq.smk                      # Main subworkflow
run_KARRseq.py                               # Standalone run script
```

## STAR Parameters for KARRseq
```json
{
    "outFilterMultimapNmax": 100,
    "outSAMattributes": "All",
    "alignIntronMin": 1,
    "scoreGapNoncan": -4,
    "scoreGapATAC": -4,
    "chimSegmentMin": 15,
    "chimJunctionOverhangMin": 15,
    "limitOutSJcollapsed": 10000000,
    "limitIObufferSize": 1500000000
}
```
