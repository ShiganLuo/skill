# Sequencing Depth Analysis Framework

## When to use

- Computing minimum sequencing depth for variant detection at a target power
- Comparing how different statistical models affect depth requirements
- Depth planning for clinical panels, liquid biopsy, or population studies
- Explaining why population genomics needs less depth than clinical calling

## Quick reference: which model for which scenario

| Scenario | Best model | Why |
|----------|-----------|-----|
| Clinical somatic (VAF 1-10%) | LOD + error-aware binomial | Matches GATK/Mutect2 logic |
| Liquid biopsy ctDNA (0.1-1%) | UMI-aware | Molecular consensus is critical |
| Germline (VAF ~50%) | LOD (vaf_model=0.5) | Standard germline calling |
| Population low-depth (1-4x) | Population imputation | LD-based imputation compensates |
| Site-level coverage | Poisson uniformity | Depth at site ≠ average depth |

## Key results (for quick reference)

| Scenario | VAF | Required depth (95% power) |
|----------|-----|---------------------------|
| Clinical somatic | 5% | 120-230x (model-dependent) |
| Clinical somatic | 1% | 570-2000x |
| Germline het | 50% | 14-17x |
| Population (1000 samples) | MAF 10% | ~1x/sample (R²≥0.80) |
| Coverage uniformity | — | 537x avg for P(site≥500x)≥0.95 |

## Framework implementation

Existing implementation at:
`.../workflow/gene/depth/simulation/depth_framework/`

Structure:
```
depth_framework/
├── models.py           # 6 statistical models (core)
├── scenarios.py        # 5 pre-built scenarios
├── depth_analyzer.py   # Unified analysis engine
└── plotting.py         # Visualization
cli.py                  # CLI entry point
```

CLI usage (requires `conda run -n ML`):
```bash
python cli.py list
python cli.py sweep clinical_somatic --vaf 0.05 --output results/
python cli.py min-depth germline --vafs 0.3 0.5 1.0
python cli.py compare --output results/
python cli.py validate clinical_somatic --depth 500 --vaf 0.05
```

## Reference files

- `references/models.md` — Mathematical formulations for all 6 models, parameter tuning guide
- `references/pitfalls.md` — Common mistakes and fixes (LOD vaf_model, overdispersion tuning, etc.)
- `references/population-vs-clinical-depth.md` — Why population genomics needs 1-4x vs clinical 30-100x