# Entrez API for GEO Metadata

GEO web pages (`geo/query/acc.cgi`) block plain `requests` — you get empty or error responses.
Use NCBI's Entrez API (via Biopython) to fetch structured XML metadata instead.

## When to Use

- Fetching GSM/GSE/GPL **metadata** (series links, SRA/BioSample cross-refs)
- NOT for downloading actual sequence data (use prefetch/aria2c for that)
- Programmatic batch access to GEO records

## Core Workflow

```python
from Bio import Entrez
Entrez.email = "your@email.com"  # required by NCBI
Entrez.api_key = "your_key"      # optional, raises rate limit 3→10 req/s

# 1. Search for UID in GDS (GEO DataSets) database
handle = Entrez.esearch(db="gds", term="GSM123456[Accession]")
results = Entrez.read(handle)
handle.close()
uid = results["IdList"][0]

# 2. Fetch the full record as XML
handle = Entrez.efetch(db="gds", id=uid, rettype="xml")
xml_text = handle.read()
handle.close()
if isinstance(xml_text, bytes):
    xml_text = xml_text.decode("utf-8")

# 3. Find related records via elink (SRA, BioSample)
handle = Entrez.elink(dbfrom="gds", db="sra", id=uid)
link_results = Entrez.read(handle)
handle.close()
# link_results[0]["LinkSetDb"][0]["Link"] contains related UIDs

# 4. Get accessions for related UIDs via esummary
handle = Entrez.esummary(db="sra", id=",".join(link_ids))
summaries = Entrez.read(handle)
handle.close()
```

## Key Entrez Functions

| Function | Purpose | DBs |
|----------|---------|-----|
| `esearch` | Find UIDs by query | gds, sra, biosample |
| `efetch` | Fetch full records | gds (XML), sra, biosample |
| `elink` | Find cross-database links | gds→sra, gds→biosample |
| `esummary` | Get record summaries | sra, biosample |

## XML Parsing

GDS efetch returns XML. Structure varies by accession type:
- **GSM** (sample): `<GeoMeta>` with sample-level metadata
- **GSE** (series): `<GeoMeta>` with series title, summary, overall design
- **GPL** (platform): platform annotation metadata

```python
import xml.etree.ElementTree as ET

tree = ET.parse("GSM123456.xml")
root = tree.getroot()

# Find GSE IDs — search all elements for text starting with "GSE"
gse_ids = [e.text.strip() for e in root.iter()
           if e.text and e.text.strip().startswith("GSE")]

# Find SRA cross-refs (SRX accessions) from enriched <RelatedRecord> elements
sra_ids = [e.text.strip() for e in root.iter("RelatedRecord")
           if e.get("db") == "sra" and e.text and e.text.strip().startswith("SRX")]

# Find BioSample cross-refs (SAMN accessions)
biosample_ids = [e.text.strip() for e in root.iter("RelatedRecord")
                 if e.get("db") == "biosample" and e.text and e.text.strip().startswith("SAMN")]
```

## Enriching XML with elink Results

After fetching the base XML via efetch, enrich it with `<RelatedRecord>` elements
so downstream parsers can extract SRA/BioSample IDs from a single file:

```python
related_parts = []
for target_db in ["sra", "biosample"]:
    elink_handle = Entrez.elink(dbfrom="gds", db=target_db, id=uid)
    elink_results = Entrez.read(elink_handle)
    elink_handle.close()

    for linkset in elink_results:
        for linksetdb in linkset.get("LinkSetDb", []):
            if linksetdb.get("DbTo") == target_db:
                link_ids = [lnk["Id"] for lnk in linksetdb.get("Link", [])]
                if link_ids:
                    sum_handle = Entrez.esummary(db=target_db, id=",".join(link_ids))
                    summaries = Entrez.read(sum_handle)
                    sum_handle.close()
                    for summary in summaries:
                        accession = summary.get("Accession",
                                    summary.get("ExpAccession", ""))
                        if accession:
                            related_parts.append(
                                f'<RelatedRecord db="{target_db}">{accession}</RelatedRecord>'
                            )

# Insert into saved XML before closing tag
if related_parts:
    related_block = "\n".join(related_parts)
    if "</GeoMeta>" in xml_text:
        xml_text = xml_text.replace("</GeoMeta>", f"{related_block}\n</GeoMeta>")
    elif "</GDS>" in xml_text:
        xml_text = xml_text.replace("</GDS>", f"{related_block}\n</GDS>")
    else:
        xml_text = xml_text.rstrip() + "\n" + related_block + "\n"
```

## Characteristics Caveat

Entrez XML does NOT contain the full "Characteristics" key-value pairs
(e.g. "tissue: liver", "strain: C57BL/6") that appear on the GEO web page.
For Characteristics, you need either:
- The SOFT format (different Entrez rettype)
- The HTML page (if accessible — often blocked)
- A supplementary SOFT file download

GSE, SRA, and BioSample IDs ARE reliably available from Entrez XML.

## Dual-Format (XML/HTML) Handling

When a tool supports both Entrez XML and legacy HTML, detect format by extension:

```python
def extract_gse_ids(filepath: str) -> List[str]:
    if filepath.endswith(".xml"):
        return extract_gse_ids_from_xml(filepath)
    # fallback to BeautifulSoup HTML parsing
    ...
```

When scanning a directory for GSM files, prefer XML over HTML:
```python
gsm_files = glob.glob("GSM*.xml") + glob.glob("GSM*.html")
seen = set()
unique = []
for f in gsm_files:
    gsm = os.path.basename(f).split(".")[0]
    if gsm not in seen:
        seen.add(gsm)
        unique.append(f)
```

## Rate Limits

- Without API key: 3 requests/second
- With API key: 10 requests/second
- Always set `Entrez.email` (NCBI requirement)
- Use `time.sleep(2 * attempt)` for exponential backoff on retries

## Biopython Dependency

```bash
pip install biopython  # provides Bio.Entrez
# or: uv pip install --python <venv>/bin/python biopython
```
