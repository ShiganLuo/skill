# Bioinformatics Result Directory Conventions

When scanning a research group's results directory, folder names and subdirectory structures encode the analysis type. This reference maps common conventions.

## Directory Name → Analysis Type

| Folder/Subfolder Name | Analysis | What It Tells You |
|---|---|---|
| `GSEA/` | Gene Set Enrichment Analysis | Pathway-level functional interpretation |
| `GSEA/DDR/` | DDR-specific GSEA | DNA Damage Response pathway enrichment |
| `GSEA/TwoGenes/` or `GSEA/EightGenes/` | Custom gene-set GSEA | Specific gene signatures being tested |
| `GSEA/2C_mouse/` | 2-cell gene enrichment | Totipotency/early embryo gene signature |
| `TE/` | Transposable Element analysis | TE subfamily expression changes (TElocal/TEcount) |
| `SNP/` | Variant/SNP calling | Somatic variants from RNA-seq or WES |
| `SNP/kegg/` | KEGG on variant genes | Pathway enrichment of mutated genes |
| `SNP/go/` | GO on variant genes | Functional annotation of mutated genes |
| `DESeq2/` | Differential expression | Standard DE analysis with volcano/heatmap |
| `volcano/` | Volcano plots | Visual summary of DE genes |
| `heatmap/` | Heatmaps | Sample clustering + gene expression patterns |
| `go/` | GO enrichment | Gene Ontology (BP/MF/CC) |
| `kegg/` | KEGG enrichment | Metabolic/signaling pathway enrichment |
| `Exome/` | Whole Exome Sequencing | Somatic mutation analysis |
| `Exome/TMB/` | Tumor Mutational Burden | Mutation load per Mb |
| `Exome/MSI/` | Microsatellite Instability | Repeat region instability |
| `TEChimeric/` | TE-chimeric reads | Transposable elements fused to genes |
| `signallingEntropy/` | Signalling entropy | Cell signaling pathway heterogeneity |
| `TE_activation/` | TE activation analysis | Global transposable element derepression |
| `Compositional/` | Cell composition | Cell type proportion changes (scRNA-seq) |
| `CCC/` | Cell-Cell Communication | Ligand-receptor interaction networks |
| `pertubation/` | Perturbation analysis | In-silico gene perturbation effects |
| `mechanisms/` | Mechanistic analysis | Downstream mechanistic exploration |
| `sv_view/` | Structural Variant view | SV visualization (IGV-style amplicon views) |
| `downDimension/` | Dimensionality reduction | PCA/tSNE/UMAP |
| `plotHeatmap/` | Repeat element heatmaps | TE-family specific heatmaps |
| `annovar/` | ANNOVAR annotation | Variant functional annotation |
| `arriba_report/` | Arriba fusion | Gene fusion detection from RNA-seq |
| `hUSI/` | Horizontal USI | Horizontal RNA transfer analysis |
| `multimap/` | Multi-mapping reads | Reads mapping to multiple genomic locations (TE-enriched) |
| `noMultimap/` | Unique-mapping reads | Strict mapping for confident peak calls |

## Common Dataset Naming (GEO)

- `GSE` prefix = GEO Series (a complete experiment)
- Same pipeline across multiple GSE = systematic re-analysis or meta-analysis
- Folder name like `GCN2` = gene name = knockout/overexpression experiment
- Suffix like `_20260422` = date-stamped re-analysis

## Constructing a Research Narrative

When asked "what story can this data tell":

1. **Map all directories** to analysis types using the table above
2. **Identify the core axes** — what biological dimensions are being measured (e.g., TE activity, DDR, epigenetics)
3. **Find the experimental conditions** — from folder names (gene knockouts), image filenames (condition comparisons like WT_vs_CKO), and GSEA gene set names (2C_mouse, SENESCENCE)
4. **Group by biological theme** — don't list projects individually; cluster them into chapters
5. **Identify gaps** — list unknowns (specific experimental conditions, missing metadata) as checklist items
6. **Map to thesis structure** — each theme becomes a results chapter

## Pitfalls

- Don't assume folder names are self-explanatory — `GNC2` vs `GCN2` may be typos for the same gene
- Compressed files (.tar.gz, .zip) should be excluded from file counts
- `~$*.xlsx` are Excel lock files, not real data
- `drawio` files often contain the project's conceptual diagrams — worth reading
- `.rnk` files = GSEA preranked input (gene rank lists)
- PPT files in result directories often contain the lab's summary figures
