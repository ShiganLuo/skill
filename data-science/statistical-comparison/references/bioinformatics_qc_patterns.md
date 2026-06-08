# Bioinformatics QC Data Analysis Patterns

## Typical RNA-seq QC Workflow

```python
# 1. Load TSV with Chinese column names
df = pd.read_csv(file_path, sep='\t', encoding='utf-8')  # fallback to 'gbk'

# 2. Filter by project
df_filtered = df[df['项目/产品名称'].str.contains('立康', na=False)]

# 3. Convert to numeric (handle empty strings)
df_filtered['Mapping rate(%)'] = pd.to_numeric(df_filtered['Mapping rate(%)'], errors='coerce')

# 4. Extract groups by sample type
group1 = df_filtered[df_filtered['样本类型'] == '组织']['Mapping rate(%)'].tolist()
group2 = df_filtered[df_filtered['样本类型'] == '石蜡包埋组织']['Mapping rate(%)'].tolist()
```

## Common QC Metrics to Compare

- Mapping rate (%)
- Exonic rate (%)
- rRNA rate (%)
- Duplication rate
- RIN value
- DV200

## Sample Types in Chinese Data

| Chinese | English |
|---------|---------|
| 组织 | Fresh tissue |
| 石蜡包埋组织 / FFPE | FFPE tissue |
| 痰液 | Sputum |
| 血液 | Blood |
| 骨髓 | Bone marrow |

## File Encoding Pitfalls

Chinese clinical data files are often:
- GBK/GB2312 encoded (Windows Chinese locale)
- UTF-8 with BOM
- Tab-separated (not comma)

Always try UTF-8 first, fallback to GBK:

```python
try:
    df = pd.read_csv(file_path, sep='\t', encoding='utf-8')
except UnicodeDecodeError:
    df = pd.read_csv(file_path, sep='\t', encoding='gbk')
```
