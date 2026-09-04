# Population-genomics module boundary reference

Use this as a decomposition example for any multi-tool population-genomics workflow in the Omics repository.

## Correct ownership

| Module | Atomic responsibility |
|---|---|
| `population_metadata` | Materialize sample-to-population map and per-population sample lists |
| `gatk/gatk_population` | Per-sample `HaplotypeCaller -ERC GVCF`, GenomicsDB import, and joint `GenotypeGVCFs` |
| `bcftools_population` | Normalize/select/filter the jointly genotyped VCF |
| `plink2_population` | VCF conversion, PCA, and GWAS performed by PLINK2 |
| `vcftools_population` | Windowed pi, Tajima's D, and pairwise Fst |
| `admixture_population` | ADMIXTURE K runs |
| `PopLDdecay_population` | Population-specific LD decay |
| `easySFS_population` | SFS preparation for demographic inference |

The subworkflow wires these modules together through paths and config dictionaries. It does not own their executable rules.

## Existing-module compatibility check

Do not reuse a similarly named rule without checking its output semantics. For population joint calling, a per-sample GATK germline module is incompatible when it:

- runs `HaplotypeCaller` without `-ERC GVCF`;
- emits and hard-filters one ordinary VCF per sample;
- has no sample map / GenomicsDB import;
- has no joint `GenotypeGVCFs` stage.

In that case, add `modules/gatk/gatk_population/` and share `../gatk.yaml`; do not place replacement GATK rules directly in the subworkflow.

## Required pre-code checklist

1. Read `modules/modules.md` and `subworkflow/subworkflow.md`.
2. List tools and decide whether each step is reusable independently.
3. Search for existing modules and inspect actual rule signatures and outputs.
4. Draw the path-level DAG before coding.
5. Define module config contracts (`indir`, `outdir`, `logdir`, `ROOT_DIR`, `Procedure`, `Params`, `genome`).
6. Only then create modules and the orchestration subworkflow.

## Verification checklist

- `subworkflow/<workflow>.smk` contains only module/config orchestration plus `rule all`.
- Every executable rule is in an atomic module and uses the canonical `run:` structure.
- New simple modules have `.smk`, `.json`, and `.yaml`; child modules reference the parent environment with the correct relative path.
- Optional branches are tested together, not only with defaults disabled.
- Dry-run uses dummy existing input files so it reaches the complete DAG rather than stopping at `MissingInputException`.
- Generated logs/test fixtures are not staged as source files.
