# Sample Metadata Description Conventions

When the user pastes a sample metadata table (GEO/SRA format) and asks for a description or "添加描述":

## Structure
- One concise paragraph (3-5 sentences)
- Chinese prose, English technical terms kept as-is

## Content Requirements
1. **Data type**: What assay (RNA-seq, ChIP-seq, ChIRP-seq, DIP-seq, etc.)
2. **Biological question**: What is being studied
3. **Experimental factors and their RELATIONSHIPS** — do not just list factors independently; explain why they are paired (e.g., "PKR is an antiviral kinase; studying DicerΔHEL1 in PKR-null cells tests whether RNAi can compensate for PKR loss")
4. **Sample groups**: Briefly mention treatment vs control, IP vs input, etc.
5. **Species/cell type**: Only if not obvious from context

## Pitfall: Listing Without Connecting
User explicitly corrected: "PKR和Dicer的关系没有交代". When multiple experimental factors exist (e.g., gene KO + viral infection, or probe type + cell condition), always explain the biological rationale for combining them. A description that lists each factor separately without explaining their interaction is incomplete.

## Example (Bad)
> These samples study DicerΔHEL1 and PKR knockout in LCMV infection. They include wildtype and PKRnull cells with MOI 0.01.

## Example (Good)
> These samples study whether the DicerΔHEL1 variant (an RNAi-enhancing truncation) can provide antiviral protection when PKR (an interferon-induced kinase that blocks viral translation) is absent. mESCs with or without PKR knockout were infected with LCMV at low MOI, allowing comparison of RNAi-mediated vs PKR-mediated antiviral pathways.

## Database Verification Workflow

When user asks to verify sample design ("确保真实设计") or when sample metadata is sparse:

1. **SRA first**: Access `https://www.ncbi.nlm.nih.gov/sra/SRR...` — these pages are usually accessible (no reCAPTCHA) and provide rich metadata: study title, sample description, library construction protocol, instrument model.
2. **GEO blocked**: GEO pages (`geo/query/acc.cgi?acc=GSM...`) often hit reCAPTCHA. Fall back to SRA.
3. **CNGB**: Chinese National GeneBank (`db.cngb.org/cnsa/`) requires login for search. If user provides CNGB metadata (with `CNP`/`CNS`/`CNX`/`CNR` accession numbers), use it — it contains project-level context (e.g., "Cell line co-culture") that significantly improves descriptions.
4. **Cross-reference**: SRA study titles and GEO series descriptions often reveal the biological question better than sample names alone.

### What to look for in DB metadata
- **Study/Project title**: The overarching research question
- **Library strategy**: RNA-Seq, ChIP-Seq, etc.
- **Library selection**: Oligo-dT (polyA), other (ribo-minus), etc.
- **Construction protocol**: Reveals subcellular fractionation, IP details, etc.
- **Source name**: Tissue/cell type context

## Context Tracking with Multiple Datasets

When multiple sample tables are in conversation and user asks a general question (e.g., "所有上面样本的目的是什么"), **check whether they mean all datasets or just the most recent one**. User corrected: "我指的是" + re-pasted the last dataset — they meant only that one. Default assumption: questions about "上面的样本" refer to the most recently pasted dataset unless explicitly plural.

## Common Sample Types Seen
- GEO samples (GSM accessions) with SRA run IDs
- ChIP-seq / ChIRP-seq with IP + Input design
- RNA-seq with disease vs control groups
- DIP-seq (DNA immunoprecipitation) for epigenetic marks
- MeRIP-seq (m6A RNA immunoprecipitation)
- ChIRP-seq (chromatin isolation by RNA purification)
- tRNA-seq for tRNA profiling
- Exome sequencing for variant calling
