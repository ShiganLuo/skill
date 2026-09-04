# Case: PacBio Telomere & Centromere Module

## Context

Adding telomere length and centromere satellite DNA analysis to the PacVar workflow.
Unlike other PacVar modules (which operate on aligned/sorted BAMs), these modules
read directly from the **raw PacBio HiFi BAM** (unaligned CCS reads).

## Module Structure

**Use established tools, not custom scripts.** The final module uses Telogator2
for telomere and RepeatMasker for centromere, with custom scripts only for
RepeatMasker output parsing and assembly-based telomere scanning.

```
modules/telomere/
├── telomere.smk          # 4 rules: telogator2 + assembly_scan + read_density + tidk
├── telomere.yaml         # conda: telogator2, tidk, pysam, numpy
├── telomere.json         # config template
└── bin/
    ├── scan_assembly_telomere.py   # Approach A: assembly contig end scanning
    └── read_density_telomere.py    # Approach B: read-level k-mer density

modules/centromere/
├── centromere.smk        # 3 rules: hifiasm + repeatmasker + centromere_extract
├── centromere.yaml       # conda: hifiasm + repeatmasker
└── bin/
    └── extract_centromere_stats.py
```

## Telomere Approaches

| Approach | Tool | Input | Output |
|----------|------|-------|--------|
| 0 (default) | Telogator2 | HiFi BAM | Per-chromosome-arm TL_p75 |
| A | Custom script | Assembly FASTA | Per-contig telomere length |
| B | Custom script | HiFi BAM | Genome-wide average |
| C | tidk | Assembly FASTA | Standardized scan |

**For mouse telomeres (30-150kb), Approach A is recommended.** HiFi reads
(~15-25kb) cannot span the full telomere for Telogator2.

## Output Paths

```
repeat/telomere/{sample_id}/
├── telogator2/           # Approach 0
│   └── tlens_by_allele.tsv
├── assembly_scan/        # Approach A
│   └── {sid}_assembly_telomere_stats.txt
├── read_density/         # Approach B
│   └── {sid}_read_telomere_stats.txt
└── tidk/                 # Approach C
    └── {sid}_tidk_telomeres.tsv

repeat/centromere/{sample_id}/
└── {sid}_centromere_stats.txt
```

## Key Design Decisions

### 1. Raw BAM input (not aligned BAM)

Telomere/centromere analysis needs **raw sequences** — aligned BAM has the read
mapped to a reference, which may clip or distort repeat regions. The module reads
from `indir` (the original PacBio BAM), not from `samtools_sort_config["outdir"]`.

```python
# PacVar.smk — telomere_config uses gatk_prepare outdir for read-based approaches
# centromere_config uses raw indir for assembly
telomere_config = {
    "indir": gatk_prepare_config["outdir"],  # aligned BAM for read-based
    "assembly_dir": centromere_outdir,        # assembly for Approach A/C
    ...
}
centromere_config = {
    "indir": indir,  # raw PacBio BAM for assembly
    ...
}
```

### 2. Use established tools

**Telomere:** Telogator2 (seed-extend matching, per-chromosome-arm output)
**Centromere:** hifiasm assembly → RepeatMasker (-species mouse)

Custom scripts are only used for:
- Assembly-based telomere scanning (Approach A)
- Read-level k-mer density (Approach B)
- Parsing RepeatMasker `.out` output into human-readable statistics

### 3. Species-specific config — MUST use scientific name

Centromere species is set in config: `Params.RepeatMasker.species`.
RepeatMasker uses this via `-species` flag. **Common names like "mouse" are ambiguous
and will fail** (RepeatMasker exits 255). Use the scientific name or NCBI taxon ID:

```json
"RepeatMasker": { "species": "Mus musculus" }
```

### 4. Centromere requires assembly first

Mouse centromere MaSat/MiSat span Mb-scale regions. HiFi reads (~15-20kb N50)
cannot span them. The module runs hifiasm assembly first, then RepeatMasker
on the assembly contigs.

## run.py Integration

```python
# In runPacVar():
skip_telomere = datajson.get("Params", {}).get("skip_telomere", False)
if not skip_telomere:
    for sample_id in samples:
        # Telogator2
        outfiles.append(f"{outdir}/repeat/telomere/{sid}/telogator2/tlens_by_allele.tsv")
        outfiles.append(f"{outdir}/repeat/telomere/{sid}/telogator2/all_final_alleles.png")
        outfiles.append(f"{outdir}/repeat/telomere/{sid}/telogator2/violin_atl.png")
        # Approach A
        outfiles.append(f"{outdir}/repeat/telomere/{sid}/assembly_scan/{sid}_assembly_telomere_stats.txt")
        # Approach B
        outfiles.append(f"{outdir}/repeat/telomere/{sid}/read_density/{sid}_read_telomere_stats.txt")
        # Approach C
        outfiles.append(f"{outdir}/repeat/telomere/{sid}/tidk/{sid}_tidk_telomeres.tsv")
        # Centromere
        outfiles.append(f"{outdir}/repeat/centromere/{sid}/{sid}.centromere_stats.txt")
```

## Pitfalls

### 1. Don't use aligned BAM for repeat analysis

Aligned reads may have soft-clipped telomeric repeats or mapping artifacts.
Always use the original unaligned BAM for repeat content analysis.

### 2. Length filter is critical for telomere calls

Without the `min_terminal_tel` filter (>=1000bp), subtelomeric scattered repeats
and ITS fragments at read ends produce false positives. Mouse telomeres are
30-150kb (129/Ola strain), so 1000bp is conservative.

### 3. Centromere requires assembly first

Mouse centromere MaSat/MiSat span Mb-scale regions. HiFi reads (~15-20kb N50)
cannot span them. The module runs hifiasm assembly first, then RepeatMasker
on the assembly contigs.

### 4. Pyright pysam import warning

When editing `bin/*.py` scripts in the IDE, Pyright reports `Import "pysam" could
not be resolved` because pysam is in the conda env, not the system Python. This
is harmless — the scripts run correctly inside `conda activate` or via Snakemake's
`--use-conda`.

### 5. hifiasm 0.25.0 needs FASTQ, not BAM

hifiasm 0.25.0 removed the `--hifi` flag (input is now positional args only) and
does NOT properly read BAM files — it produces `counted 0 distinct minimizer k-mers`
then crashes with malloc assertion failure.

**Fix**: Convert BAM to FASTQ with `samtools fastq` before passing to hifiasm:
```python
cmd0 = ["samtools", "fastq", "-@", str(threads), input.bam, "|", "gzip", "-c", ">", fq_gz]
cmd1 = ["hifiasm", "-o", params.prefix, "-t", str(threads), fq_gz]
cmd_cleanup = ["rm", "-f", fq_gz]
```

### 6. RepeatMasker -species "mouse" fails — use "Mus musculus"

RepeatMasker 4.2.3 + Dfam 3.9 cannot resolve the common name "mouse":
```
Ambiguous search term 'mouse' (found 33 results, 2 exact).
Taxon "mouse" is not defined in the current FamDB partitions present.
```
Exit code 255. The log file and RepeatMasker output are both empty.

**Fix**: `"species": "Mus musculus"` (taxon 10090) in the workflow config JSON.

### 7. run.py outfiles must match module output paths

The `outfiles` list in `run.py` must exactly match the `output:` declarations in
the module's `.smk` file. Mismatch causes Snakemake to silently skip or rebuild.
**Always update run.py when adding new rules or changing output paths.**
