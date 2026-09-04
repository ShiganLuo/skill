# QuantMS Quantitative Proteomics Workflow

QuantMS is a quantitative proteomics workflow ported from the Nextflow quantms pipeline. It supports TMT, LFQ, and DIA quantification using OpenMS.

## When to use

- User asks to run quantitative proteomics analysis (TMT, LFQ, DIA)
- User needs to process mzML files for protein identification and quantification
- User wants to use OpenMS tools for proteomics data analysis

## Workflow Steps

1. **Decoy Database Generation** - Generate decoy database for FDR control
2. **Database Search** - Search spectra against database (Comet, MSGF+, Sage)
3. **PSM Rescoring** - Rescore PSMs using Percolator
4. **PSM FDR Control** - Filter PSMs by FDR threshold
5. **Protein Inference** - Infer proteins from peptides (EpiFany)
6. **Protein Quantification** - Quantify proteins (ProteomicsLFQ or ProteinQuantifier)
7. **Statistical Analysis** - MSstats for statistical analysis

## File Structure

```
workflow/Omics/
├── config/QuantMS.json                    # Configuration template
├── subworkflow/QuantMS.smk                # Main subworkflow
└── modules/openms/
    ├── decoydatabase/
    │   ├── decoydatabase.smk
    │   ├── decoydatabase.json
    │   └── openms.yaml
    ├── searchengine/
    │   ├── searchengine.smk
    │   ├── searchengine.json
    │   └── openms.yaml
    ├── psmrescoring/
    │   ├── psmrescoring.smk
    │   ├── psmrescoring.json
    │   └── openms.yaml
    ├── psmfdr/
    │   ├── psmfdr.smk
    │   ├── psmfdr.json
    │   └── openms.yaml
    ├── proteininference/
    │   ├── proteininference.smk
    │   ├── proteininference.json
    │   └── openms.yaml
    ├── quantification/
    │   ├── quantification.smk
    │   ├── quantification.json
    │   └── openms.yaml
    └── msstats/
        ├── msstats.smk
        ├── msstats.json
        └── openms.yaml
```

## Usage

### Command Line

```bash
python run.py \
  -m /path/to/mzml_directory \
  -w QuantMS \
  -o output \
  -t 8 \
  --conda-prefix /data/pub/zhousha/env/openms \
  --genome.fasta /path/to/protein_database.fasta \
  --quantification_method lfq \
  --search_engines comet
```

### Input Requirements

- mzML files in the input directory (one per sample)
- Protein database in FASTA format
- Sample IDs should match mzML filenames (without extension)

### Key Configuration Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `quantification_method` | Quantification type (tmt/lfq/dia) | lfq |
| `search_engines` | Comma-separated search engines | comet |
| `Params.decoy_database.method` | Decoy generation method | shuffle |
| `Params.psm_fdr_control.fdr` | PSM FDR threshold | 0.01 |
| `Params.protein_inference.method` | Protein inference method | epifany |
| `Params.skip_post_msstats` | Skip MSstats analysis | false |

## Pitfalls

1. **mzML file naming**: Sample IDs must match mzML filenames exactly
2. **Decoy database**: Must be generated before search engines run
3. **Search engine selection**: Only one search engine output is used for downstream analysis
4. **Conda environment**: All modules use openms-thirdparty=3.1.0
5. **Experimental design**: For TMT, channel annotation must be provided

## References

- Original Nextflow pipeline: https://github.com/bigbio/quantms
- OpenMS documentation: https://openms.de/documentation/
