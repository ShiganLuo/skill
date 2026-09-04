# Sample Meta Editor Pattern (Table + TSV Dual Mode)

## Overview
Edit structured metadata (like bioinformatics sample info) with both a table editor and raw TSV text editor. Supports multiple modes (FASTQ, PacBio, MS, scRNA-seq) with different column templates.

## Data Model

```sql
CREATE TABLE sample_meta (
    id           BIGINT       NOT NULL AUTO_INCREMENT,
    project_id   BIGINT       NOT NULL,
    name         VARCHAR(128) NOT NULL,
    meta_mode    VARCHAR(32)  NOT NULL DEFAULT 'fastq',
    meta_content TEXT         NOT NULL COMMENT 'TSV content',
    description  VARCHAR(512) DEFAULT NULL,
    created_by   BIGINT       DEFAULT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_sample_meta_project (project_id)
);
```

## Mode Column Templates

```typescript
const META_MODE_COLUMNS: Record<string, string[]> = {
  fastq: ['sample_id', 'design', 'fastq_1', 'fastq_2', 'group', 'organism'],
  pacbio: ['sample_id', 'design', 'bam', 'pbi', 'group', 'organism'],
  ms: ['sample_id', 'ms_file', 'organism'],
  scrnaseq: ['sample_id', 'fastq_dir', 'sample_prefix', 'design', 'group', 'organism'],
}
```

## Frontend: Table Editor

Use a raw HTML `<table>` with `<input>` cells (not el-table) for spreadsheet-like editing:

```vue
<table class="meta-table">
  <thead>
    <tr>
      <th style="width: 40px">#</th>
      <th v-for="(col, ci) in metaColumns" :key="ci">
        <span>{{ col }}</span>
        <el-button link size="small" type="danger" @click="removeColumn(ci)" 
                   v-if="!isFixedColumn(col)">
          <el-icon><Close /></el-icon>
        </el-button>
      </th>
      <th><el-button link size="small" @click="addColumn"><el-icon><Plus /></el-icon></el-button></th>
    </tr>
  </thead>
  <tbody>
    <tr v-for="(row, ri) in metaRows" :key="ri">
      <td>{{ ri + 1 }}</td>
      <td v-for="(col, ci) in metaColumns" :key="ci">
        <input v-model="metaRows[ri][ci]" class="meta-cell" :placeholder="col" />
      </td>
      <td><el-button link size="small" type="danger" @click="removeRow(ri)"><el-icon><Close /></el-icon></el-button></td>
    </tr>
  </tbody>
</table>
```

```css
.meta-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.meta-table th, .meta-table td {
  border: 1px solid #ebeef5;
  padding: 4px 8px;
  white-space: nowrap;
}
.meta-table th {
  background: #f5f7fa;
  font-weight: 600;
}
.meta-cell {
  border: none;
  outline: none;
  width: 100%;
  font-size: 13px;
  font-family: monospace;
  padding: 2px 0;
  background: transparent;
}
.meta-cell:focus {
  background: #ecf5ff;
}
```

## TSV ↔ Table Conversion

```typescript
const tsvToTable = (tsv: string) => {
  const lines = tsv.trim().split('\n')
  if (lines.length === 0) return
  metaColumns.value = lines[0].split('\t')
  metaRows.value = []
  for (let i = 1; i < lines.length; i++) {
    const cells = lines[i].split('\t')
    while (cells.length < metaColumns.value.length) cells.push('')
    metaRows.value.push(cells.slice(0, metaColumns.value.length))
  }
  if (metaRows.value.length === 0) {
    metaRows.value = [metaColumns.value.map(() => '')]
  }
}

const tableToTsv = () => {
  const header = metaColumns.value.join('\t')
  const rows = metaRows.value.map(r => r.join('\t')).join('\n')
  return header + '\n' + rows
}
```

## Mode Switching

When switching modes, only replace columns if table is empty or has minimal content:

```typescript
const handleModeChange = (mode: string) => {
  if (metaColumns.value.length === 0 || metaColumns.value.length <= 1) {
    metaColumns.value = [...(META_MODE_COLUMNS[mode] || ['sample_id'])]
    metaRows.value = [metaColumns.value.map(() => '')]
  }
}
```

## Sample Count

```typescript
const countSamples = (content: string) => {
  if (!content) return 0
  const lines = content.trim().split('\n')
  return Math.max(0, lines.length - 1)  // minus header
}
```

## Pitfalls
- `sample_id` column is always fixed (cannot be deleted)
- TSV content stores header + data rows (first line is column names)
- Mode switching doesn't clear existing data (only fills empty table)
- Import TSV dialog is separate from the edit dialog
