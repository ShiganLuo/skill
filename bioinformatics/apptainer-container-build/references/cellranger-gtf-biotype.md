# Cell Ranger mkref GTF Biotype Compatibility

## Problem

Cell Ranger's reference building script (`cellranger_ref.py`) filters GTF by biotype to keep only protein_coding, lncRNA, and IG/TR genes. The filter uses regex matching on GTF attributes.

## GENCODE vs Ensembl Attribute Names

| Source | Gene biotype attribute | Transcript biotype attribute |
|--------|----------------------|---------------------------|
| GENCODE (human/mouse) | `gene_type "protein_coding"` | `transcript_type "protein_coding"` |
| Ensembl (macaque, etc.) | `gene_biotype "protein_coding"` | `transcript_biotype "protein_coding"` |

## Symptom

When using an Ensembl GTF with Cell Ranger mkref:
```
Filtering GTF by biotype ...
  0 genes pass biotype filter
Error: The supplied GTF file does not contain any exon features
```

## Fix

Update the regex patterns in `cellranger_ref.py` to match both attribute names:

```python
# Before (GENCODE only):
gene_pattern = re.compile(rf'gene_type "({BIOTYPE_PATTERN})"')
tx_pattern = re.compile(rf'transcript_type "({BIOTYPE_PATTERN})"')

# After (GENCODE + Ensembl):
gene_pattern = re.compile(rf'(?:gene_type|gene_biotype) "({BIOTYPE_PATTERN})"')
tx_pattern = re.compile(rf'(?:transcript_type|transcript_biotype) "({BIOTYPE_PATTERN})"')
```

## Verification

```bash
# Check which attribute names your GTF uses
grep -v "^#" <gtf> | head -3 | cut -f9 | grep -oP 'gene_\w+|transcript_\w+' | sort -u
```

## Affected Species/Assemblies

- Macaque: Mmul_10 (Ensembl) — uses `gene_biotype`/`transcript_biotype`
- Any non-GENCODE Ensembl GTF — uses `gene_biotype`/`transcript_biotype`
- GENCODE GTFs (GRCh38, GRCm39) — use `gene_type`/`transcript_type`
