# MSI Feature Engineering Reference

## bMSI Data Simulation and Feature Engineering

### Data Sources
- Blood samples: normal cell-free DNA (cfDNA) distributions
- Tissue samples: MSI-H tumor distributions
- Simulation: mix tissue MSI signal into blood at varying AF (allele frequency)

### Simulated Data Generation (MoniPlasmaBlood)
For each blood sample:
- 45% probability: mix tissue MSI signal at AF=0.05/0.10/0.15
- 55% probability: keep original blood data
- sim_run_site(): add tissue reads scaled by AF to blood distribution

### Features per Locus
1. **Distribution features**: normalized counts for positions 0 to mss-1
2. **msimssRatio**: msiPatternCount / msi2mssPatternCount
3. **msiRatio**: msiPatternCount / (msi2mssPatternCount + msiPatternCount)
4. **remainderRatio**: (msi2mssPatternCount + msiPatternCount) / Depth

### Pattern Classification
- msi pattern: repeat lengths 0 to msi_threshold
- msi2mss pattern: transitional lengths (msi to mss-1)
- mss pattern: lengths ≥ mss_threshold
- Classification: N_msiPatternRatio ≥ threshold → Class=1 (MSI)

### Model Training
- XGBoost (n_estimators=20, max_depth=6, binary:logistic)
- Per-locus models (each MSI site has its own model)
- Model selection: only use models with AUC ≥ 0.8
- Site filtering: Ratio = msiRatio/mssRatio ≥ 1.9

### BAM Path Resolution
For different sample types:
- BL: site_path → replace path components → .bam
- PCR/renqun: CRC_path / cancer / 4_realign_bam / *.bam
- Pattern matching: use `BL_PREFIX_USE_RESOLVE_BL` to dispatch between resolvers
