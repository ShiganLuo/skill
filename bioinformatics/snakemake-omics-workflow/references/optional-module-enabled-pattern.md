# Optional Module Enabled Pattern

## JSON Config Convention

Each module's `enabled` lives in its own `Params` section — NOT in a separate umbrella key.

```json
{
    "Params": {
        "TEtranscripts": {"enabled": true},
        "DESeq2": {"enabled": true},
        "StringTie": {"enabled": true},
        "arriba": {"enabled": true},
        "gatk_RNAseq": {"enabled": true},
        "report": {"enabled": true},
        "function": {
            "GRCm39": {"enabled": true, "species": "mouse"},
            "GRCh38": {"enabled": true, "species": "human"}
        }
    }
}
```

## node.py Wiring

Read each module's own `enabled` with default `True`:
```python
_te_enabled = datajson.get("Params", {}).get("TEtranscripts", {}).get("enabled", True)
_transcripts_enabled = datajson.get("Params", {}).get("StringTie", {}).get("enabled", True)
_fusion_enabled = datajson.get("Params", {}).get("arriba", {}).get("enabled", True)
_variation_enabled = datajson.get("Params", {}).get("gatk_RNAseq", {}).get("enabled", True)
_deseq2_enabled = datajson.get("Params", {}).get("DESeq2", {}).get("enabled", True)
_report_enabled = datajson.get("Params", {}).get("report", {}).get("enabled", True)
```

## Downstream Priority Principle

Snakemake DAG auto-resolves dependencies. Downstream `enabled=true` automatically pulls in upstream outputs as intermediate dependencies. Do NOT gate downstream on upstream:
```python
# WRONG
_deseq2_enabled = ... and _te_enabled

# CORRECT — each module independently controlled
_deseq2_enabled = datajson.get("Params", {}).get("DESeq2", {}).get("enabled", True)
```

## outfiles Tracking

Track upstream outputs when ANY downstream consumer is enabled:
```python
if _te_enabled or _deseq2_enabled:
    outfiles.append(f"{outdir}/counts/{genome}/TEcount/all_TEcount.tsv")
    outfiles.append(f"{outdir}/counts/{genome}/TElocal/all_TElocal.tsv")
```

## Output Mapping (RNAseq example)

| Params key | Output files |
| --- | --- |
| `TEtranscripts.enabled` | `counts/{genome}/TEcount/all_TEcount.tsv`, `counts/{genome}/TElocal/all_TElocal.tsv` |
| `DESeq2.enabled` | `diff_expression/{genome}/{ctr}_vs_{exp}/DESeq2.done` |
| `function.<org>.enabled` | `function/{genome}/{pair}/go_*.png`, `kegg_*.png`, `GSEA/*.jpeg`, `*.csv` |
| `StringTie.enabled` | `transcripts/{genome}/stringtie_merged.gtf`, `TE_chimeric/*.png/*.tsv` |
| `arriba.enabled` | `fusion/{genome}/arriba_report/arriba_fusion_report.html`, `*_passed_fusions.tsv` |
| `gatk_RNAseq.enabled` | `variation/germline_snv_indel_RNAseq/{genome}/{sample}/*.filtered.vcf.gz` |
| `report.enabled` | `results/{genome}/RNAseq_report.pptx` |

## Anti-pattern: Separate Umbrella Section

Do NOT create `Params.RNAseq.enabled` or similar umbrella keys. Each module owns its control.
