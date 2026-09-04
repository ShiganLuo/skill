# Mouse Repetitive Sequences Reference

## Telomere

Same as human: (TTAGGG)n. Both strands present:
- G-rich: TTAGGGTTAGGG...
- C-rich: CCCTAACCCTAA...

Strain-dependent length:
| Strain    | Telomere Length | Notes |
|-----------|----------------|-------|
| CAST/EiJ  | ~150 kb        | Longest common lab strain |
| 129/Ola   | ~50-100 kb     | E14 ES cells derived from this |
| C57BL/6J  | ~30-50 kb      | Most common reference strain |
| FVB/N     | ~25-40 kb      | |

## Centromere — Major Satellite (MaSat)

Pericententromeric heterochromatin. ~234bp monomer. GA-rich strand.
Repeats ~3-6% of mouse genome.

Simplified consensus (from RepeatMasker/Dfam):
```
GAAAAACCTCGAGAATGGCGAGAAACTGAGAAGCCCGCAACGAATGGGATGTGAATATCCTGATGAAATGGAATGCACTGGCTATGATGCAAGAGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGACTAGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGGAATGG
```

Key feature: Long internal tandem of "AATGG" pentamers.

Dfam accession: DF0000001 (MURSatellite1)

## Centromere — Minor Satellite (MiSat)

Centromeric core. ~120bp monomer. GC-rich strand.

Simplified consensus:
```
GAAAATGATAAAAACCACACTGTATGGAAATGACATTTATAATATCATATGTTTTCATCAACACAAAAATTTAAAAAATGTTTTAATATATTTTACTGTAAAAGTGACATCTATGGAAAAAAT
```

Dfam accession: DF0000002 (MURSatellite2)

## Human Alpha-Satellite (for comparison)

~171bp monomer. Found at all human centromeres.
Higher-order repeat structure varies by chromosome.

## References

- Dfam: https://www.dfam.org/
- RepBase: https://www.girinst.org/repbase/
- Mouse T2T: https://www.ncbi.nlm.nih.gov/assembly/GCF_000001635.27
