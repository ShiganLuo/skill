# Case Study: Porting nf-core/pacvar to Omics Snakemake

## Source Nextflow pipeline

Location: `/data/pub/zhousha/20251218_PacBio/workflow/pacvar/`

### Nextflow DAG (from `workflows/pacvar.nf`)

```
Input BAM
  → PBMM2_ALIGN (pbmm2)
  → SAMTOOLS_SORT
  → SAMTOOLS_INDEX
  → [if wgs workflow]:
      → [if !skip_snp]:
          BAM_SNP_VARIANT_CALLING (deepvariant OR gatk4 HaplotypeCaller)
          → [if !skip_phase]: HIPHASE_SNP
      → [if !skip_sv]:
          BAM_SV_VARIANT_CALLING (pbsv_discover → pbsv_call → bgzip → bcftools_index)
          → [if !skip_phase]: HIPHASE_SV
  → [if repeat workflow]:
      REPEAT_CHARACTERIZATION (trgt_genotype → samtools_sort → samtools_index → bcftools_sort → bcftools_index → trgt_plot)
```

### Nextflow modules used

| Nextflow module | Snakemake module created | Notes |
|---|---|---|
| PBMM2_ALIGN | modules/pbmm2/ | New tool |
| SAMTOOLS_SORT | modules/samtools/sort/ | Subdir of existing |
| SAMTOOLS_INDEX | modules/samtools/sort/ | Same file, separate rule |
| DEEPVARIANT_RUNDEEPVARIANT | modules/deepvariant/ | New tool |
| GATK4_HAPLOTYPECALLER | modules/gatk/gatk_germline/ | Reused existing |
| PBSV_DISCOVER | modules/pbsv/ | New tool |
| PBSV_CALL | modules/pbsv/ | Same module |
| TABIX_BGZIP | modules/tabix/ | New tool |
| BCFTOOLS_INDEX | modules/bcftools/ | New tool |
| HIPHASE | modules/hiphase/ | New, used twice (SNP+SV) |
| TRGT_GENOTYPE | modules/trgt/ | New tool |
| TRGT_PLOT | modules/trgt/ | Same module |

### Key mapping decisions

1. **samples vs paired/single**: PacBio data is always single-end BAM, so `samples` list replaces `paired_samples`/`single_samples`.

2. **Input format**: Nextflow uses samplesheet CSV; Snakemake expects `indir/{sample_id}/{sample_id}.bam`.

3. **Conditional branches**: Nextflow `if (params.X)` → Snakemake `if not config.get("Params", {}).get("skip_X")`.

4. **Module reuse**: GATK HaplotypeCaller reused from existing `modules/gatk/gatk_germline/gatk_germline.smk`.

5. **Same module, different config**: hiphase imported twice with different `bam_dir`/`vcf_dir` for SNP vs SV phasing.

## Files created

```
modules/pbmm2/{pbmm2.smk,pbmm2.json,pbmm2.yaml}
modules/pbsv/{pbsv.smk,pbsv.json,pbsv.yaml}
modules/deepvariant/{deepvariant.smk,deepvariant.json,deepvariant.yaml}
modules/bcftools/{bcftools.smk,bcftools.json,bcftools.yaml}
modules/tabix/{tabix.smk,tabix.json,tabix.yaml}
modules/hiphase/{hiphase.smk,hiphase.json,hiphase.yaml}
modules/trgt/{trgt.smk,trgt.json,trgt.yaml}
modules/samtools/sort/{samtools_sort.smk,samtools_sort.json}
subworkflow/PacVar.smk
config/PacVar.json
run.py (modified: +runPacVar, +PacVar choice)
```
