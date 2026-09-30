# LRtranscriptome — Long-Read Full-Length Transcriptome Workflow

## Pipeline DAG

```
FASTQ (PacBio HiFi / ONT)
    ↓
LRtranscriptome_minimap2_align  (minimap2 -ax map-ont/map-hifi → samtools sort/index)
    ↓
LRtranscriptome_stringtie_assemble  (StringTie -L, per-sample assembly)
    ↓
LRtranscriptome_stringtie_merge  (StringTie --merge, cross-sample merge)
    ↓
LRtranscriptome_stringtie_quant  (StringTie -e -B -L, re-quantify with merged GTF)
```

## Modules Created

### minimap2 module (modules/minimap2/)

3-file structure: minimap2.smk, minimap2.json, minimap2.yaml

Rules:
- minimap2_align: FASTQ → sorted BAM + BAI (minimap2 piped to samtools sort/index)
- minimap2_result: aggregation rule

Key config:
- Params.minimap2.preset: map-ont (default), map-hifi, map-pb
- genome.fasta: reference genome FASTA

### StringTie longread sub-module (modules/StringTie/longread/)

Sub-module sharing parent conda env via conda: "../StringTie.yaml"

Rules:
- stringtie_lr_assemble: per-sample transcript assembly (-L flag)
- stringtie_lr_merge: merge GTFs across samples (--merge)
- stringtie_lr_quant: re-quantify with merged GTF (-e -B -L)
- stringtie_lr_result: aggregation rule

Key config:
- upstream_indir: directory containing sorted BAMs from minimap2
- merged_gtf: path to merged GTF (output of merge rule)

## Why a Separate longread Sub-module

StringTie existing stringTie rule expects {sample_id}.bam as input, but minimap2 outputs {sample_id}.sorted.bam. Creating a separate sub-module:
1. Avoids modifying existing StringTie module (other workflows depend on it)
2. Adds long-read specific flags (-L, -e -B -L)
3. Handles .sorted.bam naming explicitly
4. Keeps merge and quant rules (not in original StringTie module)

## Config Structure (config/LRtranscriptome.json)

```json
{
    "genome": {
        "default": "GRCm39",
        "references": {
            "GRCm39": { "fasta": "...", "gtf": "..." },
            "GRCh38": { "fasta": "...", "gtf": "..." }
        }
    },
    "Params": {
        "skip_quant": false,
        "minimap2": { "preset": "map-ont", "extra": "" }
    },
    "Procedure": {
        "minimap2": null,
        "samtools": null,
        "stringtie": null
    }
}
```

## runLRtranscriptome() in node.py

Outfiles pattern:
- {outdir}/alignment/{sid}/{sid}.sorted.bam + .bai
- {outdir}/stringtie/raw/{sid}/{sid}.gtf
- {outdir}/stringtie/stringtie_merged.gtf
- {outdir}/quantification/{sid}/{sid}.gene_abund.tab
- {outdir}/quantification/{sid}/{sid}.quant.gtf

## Meta File for SE Long-Read Data

```tsv
sample_id\tdata_id\tdesign\tfastq_1\tfastq_2\torganism
Sample1\tSample1\t\tfastq/Sample1/Sample1_1.fq.gz\tfastq/Sample1/not_exist.fq.gz\tMus musculus
```

- fastq_2 must be a non-existent placeholder (MetaUtil treats as SE)
- organism column is REQUIRED (MetaUtil throws KeyError without it)

## Pitfalls

1. Input function os.path.exists breaks dry-run - Use direct path patterns, not input functions with existence checks
2. MetaUtil SE naming - Creates {sid}.single.fq.gz, not {sid}.fq.gz
3. BAM naming mismatch - StringTie expects .bam, minimap2 outputs .sorted.bam
4. minimap2 piped to samtools - Single script with | pipe, not separate commands
