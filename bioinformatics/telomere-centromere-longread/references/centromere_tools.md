# Centromere Length Identification: Open-Source Tools

## Tool Landscape

| Tool | Input | Method | Species | Best For |
|------|-------|--------|---------|----------|
| RepeatMasker | Assembly FASTA | Repeat library annotation | Any with library | Basic satellite quantification |
| TRF | FASTA | Tandem repeat detection | Any | HOR structure discovery |
| TRASH | HiFi reads | Satellite k-mer clustering | Any | Read-level satellite annotation |
| SDM | Assembly + reads | Satellite DNA modeling | Any | HOR structure + centromere boundaries |
| HiCAT | HiFi reads + assembly | k-mer spectrum + read mapping | Any | T2T centromere annotation |
| cenSat / t2t_censat | T2T assembly | Satellite annotation framework | Human (CHM13) | Per-chromosome centromere classification |
| CenFinder | Assembly + Hi-C | Hi-C contact pattern | Plants | Centromere positioning |
| centromFind | T2T assembly + Hi-C | Hi-C contact matrix features | Any with Hi-C | Centromere localization |
| fw_regions (tolkit) | Assembly | Low-complexity region detection | Any | Quick centromere/telomere/satellite scan |
| CENTAUR | Assembly + Hi-C | Centromere annotation | Any | Centromere boundary detection |

## Key Publications

- **T2T-CHM13 centromere**: Altemose et al., Science 2022 — first complete human centromere sequences
- **Mouse centromeres**: Mouse Major Satellite ~234bp repeat unit, Minor Satellite ~120bp
- **CenSat annotation**: Miga Lab's hierarchical centromeric satellite annotation (hor, mon, censat levels)

## RepeatMasker Approach (Current Pipeline)

Our `extract_centromere_stats.py` uses keyword matching on RepeatMasker output:
- Mouse: MSAT, Major_satellite, GSAT → MajorSatellite; SATMIN, Minor_satellite → MinorSatellite; SAT, SATB → Pericentromeric
- Human: ALR, Alpha → AlphaSatellite; SATA, SATR, HSAT → Satellite

Limitations:
- Keyword matching is imprecise (SAT matches broadly)
- MinorSatellite often missing (RepeatMasker library coverage issue)
- Cannot identify centromere POSITION, only satellite QUANTITY

### Per-Contig Satellite Block Analysis (Added 2026-06-27)

`extract_centromere_stats.py` now includes per-contig satellite block detection:
- Groups nearby satellite repeat hits into blocks (default: max 50kb gap)
- Reports blocks >= 100kb (configurable via `--min_block_len`)
- Shows satellite composition per block (GSAT_MM, IMPB_01, ZP3AR, etc.)

```bash
python extract_centromere_stats.py \
  --rm_out RepeatMasker/asm.bp.p_ctg.fa.out \
  --output centromere_stats.txt \
  --species mouse \
  --max_gap 50000 \
  --min_block_len 100000
```

Output includes:
- Per-block: contig, start, end, length, number of regions, satellite types
- Summary: total satellite block bp, number of blocks

**Interpretation guide:**
- Pure GSAT_MM blocks starting at position 1 → contig is mostly centromeric satellite array fragment
- Mixed blocks (IMPB_01 + ZP3AR + MMSAT4) → pericentromeric transition zone
- Blocks with `start=1` and `length ≈ contig_length` → entire contig is satellite DNA, assembly broke within centromere
- For mouse, expect blocks of 100kb-3Mb; larger blocks suggest better assembly continuity

## Recommendations for Non-T2T Assemblies

For centromere length from non-T2T assemblies:
1. **RepeatMasker + custom extraction** (our current approach) — adequate for satellite quantity
2. **Per-contig satellite block analysis** — identifies potential centromere regions and boundaries
3. **TRF on assembly** — can reveal HOR structure if contigs span centromeric regions
4. **SDM** — more sophisticated satellite modeling, can handle fragmented assemblies
5. **fw_regions** — quick scan for low-complexity regions including centromeres

For precise centromere positioning:
1. **Hi-C based** (CenFinder, centromFind) — requires Hi-C data
2. **CENP-A ChIP-seq** — epigenetic mark, most definitive but requires wet lab
3. **T2T assembly** — only way to fully resolve centromeric satellite arrays

## Biological Significance of Centromere Length

Centromere length measurements are relevant for:
- **Chromosome stability**: Too-short centromeres → insufficient kinetochore assembly → missegregation
- **Cell division fidelity**: Centromere size affects CENP-A nucleosome count → kinetochore size → spindle attachment
- **Genome evolution**: Centromere length varies across species and within species, linked to speciation
- **Cancer genomics**: Centromere instability (length changes, structural rearrangements) is a tumor hallmark
- **Comparative genomics**: Comparing centromere satellite arrays between conditions (e.g., drug treatments) can reveal genomic stability effects

**For non-T2T assemblies**: Centromere length measurement is limited because assemblies often break within centromeric satellite arrays. The per-contig block analysis provides a lower bound estimate of centromere size.
