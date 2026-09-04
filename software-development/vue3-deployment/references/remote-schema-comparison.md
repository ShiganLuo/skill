# Remote Docker MySQL Schema Comparison

When the remote database was initialized from an older `blog.sql`, columns may be missing. The SQL file is only executed on first deploy (`docker-entrypoint-initdb.d`); subsequent changes require manual `ALTER TABLE`.

## Compare remote vs local schema

```bash
# Get remote table columns via SSH + docker exec
ssh -p PORT user@host "docker exec blog_mysql mysql -uroot -pPASS blog -e 'DESCRIBE table_name;'"

# Get local table columns from blog.sql
awk '/CREATE TABLE.*table_name/,/);/' blog.sql | grep -E '^\s+`\w+`' | awk '{print $1}' | tr -d '`'
```

## Batch comparison script

```python
from hermes_tools import terminal
import re

sql = terminal("cat blog.sql")
lines = sql['output'].split('\n')

tables = ['users', 'roles', 'permissions', 'articles', 'comments', ...]

for tbl in tables:
    # Find CREATE TABLE block manually (line-by-line, stop at );)
    in_block = False
    block = []
    for line in lines:
        if 'CREATE TABLE' in line and tbl in line:
            in_block = True
            block = [line]
            continue
        if in_block:
            block.append(line)
            if line.strip().startswith(');'):
                break

    # Extract columns (match `col_name` TYPE pattern)
    tcols = []
    for line in block:
        m = re.match(r'\s+`(\w+)`\s+\w+', line)
        if m:
            tcols.append(m.group(1))

    # Get remote columns
    r = terminal(f"ssh ... 'docker exec blog_mysql mysql ... -e \"DESCRIBE {tbl};\"'")
    rcols = [line.split('\t')[0].strip() for line in r['output'].strip().split('\n')[1:] if line.strip()]

    missing = [c for c in tcols if c not in rcols]
    if missing:
        print(f"表 {tbl}: 远程缺少 {missing}")
```

## Pitfalls

- **Regex must stop at first `);`** — SQL file has multiple CREATE TABLE blocks. A greedy regex captures all blocks and reports false "missing" columns from other tables.
- **Mixed indentation** — some lines use tabs, some spaces. Use `\s+` in regex, not literal spaces.
- **Existing data blocks NOT NULL + FK** — when adding a NOT NULL column with FK constraint to a table that already has rows:
  1. Add column as `DEFAULT NULL` first
  2. `UPDATE table SET new_col = value WHERE new_col IS NULL`
  3. `ALTER TABLE MODIFY COLUMN new_col BIGINT NOT NULL`
  4. Then add UNIQUE KEY and FOREIGN KEY constraints
- **`information_schema` for reliable column listing**:
  ```sql
  SELECT COLUMN_NAME FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA='blog' AND TABLE_NAME='blog_settings'
  ORDER BY ORDINAL_POSITION;
  ```
