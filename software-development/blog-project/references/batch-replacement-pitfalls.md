# Batch Code Replacement Pitfalls

When doing find-and-replace across many Vue/TS files (e.g. `ElNotification` → `ElMessage`):

## Common Issues

1. **Different formatting patterns**: Same component may use `font-weight: 600` (kebab-case) in some files and `fontWeight: 600` (camelCase) in others. Regex must handle both.

2. **Multiline patterns**: Some calls span multiple lines:
```js
ElNotification({
  offset: 60,
  title: "提示",
  message: h("div", { style: "color: #7ec050; fontWeight: 600" }, "操作成功"),
});
```
While others are single-line. Use `re.DOTALL` or `\s*` patterns.

3. **Ternary expressions in message**:
```js
message: h("div", { style: "..." }, form.id ? "修改成功" : "留言成功")
```
Can't use simple string capture — need to match the full expression.

4. **Duplicate imports**: After replacement, check for:
```bash
grep -rn "import.*ElMessage" src/ --include="*.vue" | awk -F: '{print $1}' | sort | uniq -c | sort -rn
```

5. **Unused `h` import**: If `h()` calls were removed, clean up:
```bash
# Check if h is still used
grep -rn "h(" file.vue | grep -v "import\|//"
# If not, remove from import
```

6. **`cat -A` display issue**: Backticks show as `***` in `cat -A` output. Use `python3 -c "print(repr(line))"` or hex dump to verify actual content.

## Verification Script

```bash
#!/bin/bash
# After batch replacement, verify:
# 1. No remaining old patterns
grep -rn "ElNotification" src/ --include="*.vue" | grep -v "import"
# 2. No duplicate imports
grep -rn "import.*ElMessage" src/ --include="*.vue" | awk -F: '{print $1}' | sort | uniq -c | sort -rn
# 3. Build succeeds
pnpm run build
```
