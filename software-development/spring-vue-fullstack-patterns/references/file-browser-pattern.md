# File Browser Pattern (Directory Tree + Download)

## Overview
Scan server directories and display as a browsable tree in the frontend, with single-file and batch download support.

## Backend: Directory Scanning

```java
// DTO
public class FileTreeNode {
    private String name;
    private String path;       // relative path for display
    private String filePath;   // absolute path for download
    private boolean directory;
    private Long size;
    private String fileType;
    private String modifiedAt;
    private List<FileTreeNode> children;
}

// Service: recursive scan
private List<FileTreeNode> scanDirectory(Path dir, Path rootDir) {
    List<FileTreeNode> nodes = new ArrayList<>();
    try (Stream<Path> entries = Files.list(dir)) {
        entries.sorted((a, b) -> {
            boolean aDir = Files.isDirectory(a);
            boolean bDir = Files.isDirectory(b);
            if (aDir != bDir) return aDir ? -1 : 1;  // directories first
            return a.getFileName().toString().compareToIgnoreCase(b.getFileName().toString());
        }).forEach(entry -> {
            FileTreeNode node = new FileTreeNode();
            node.setName(entry.getFileName().toString());
            node.setPath(rootDir.relativize(entry).toString());
            node.setFilePath(entry.toString());
            node.setDirectory(Files.isDirectory(entry));
            
            if (Files.isDirectory(entry)) {
                node.setChildren(scanDirectory(entry, rootDir));
            } else {
                try { node.setSize(Files.size(entry)); } catch (IOException e) { node.setSize(0L); }
                node.setFileType(getFileExtension(entry.getFileName().toString()));
                try {
                    node.setModifiedAt(Files.getLastModifiedTime(entry).toInstant()
                        .atZone(ZoneId.systemDefault()).format(DATE_FMT));
                } catch (IOException e) { /* ignore */ }
            }
            nodes.add(node);
        });
    } catch (IOException e) {
        log.warn("扫描目录失败: {}", dir, e);
    }
    return nodes;
}
```

## Backend: Batch Download (ZIP)

```java
public ByteArrayOutputStream batchDownloadByPaths(List<String> filePaths, long maxTotalBytes) {
    long totalSize = 0;
    List<Path> validPaths = new ArrayList<>();
    for (String fp : filePaths) {
        Path p = Paths.get(fp);
        if (Files.exists(p) && Files.isRegularFile(p)) {
            totalSize += Files.size(p);
            validPaths.add(p);
        }
    }
    if (totalSize > maxTotalBytes) {
        throw new RuntimeException("文件总大小超过限制");
    }
    
    try (ByteArrayOutputStream baos = new ByteArrayOutputStream();
         ZipOutputStream zos = new ZipOutputStream(baos)) {
        for (Path p : validPaths) {
            zos.putNextEntry(new ZipEntry(p.getFileName().toString()));
            Files.copy(p, zos);
            zos.closeEntry();
        }
        zos.finish();
        return baos;
    }
}
```

## Frontend: Tree Display with el-table

The tree is flattened into a list for el-table display (el-table doesn't support tree expansion well for dynamic data):

```typescript
// Flatten tree to list with indentation
const flattenNode = (node: FileTreeNode, flat: any[], indent: string) => {
  if (node.directory && node.children?.length) {
    flat.push({ ...node, rowKey: 'dir-' + node.path, _indent: indent })
    for (const child of node.children) {
      flattenNode(child, flat, indent + '  ')
    }
  } else if (!node.directory) {
    flat.push({ ...node, rowKey: 'file-' + node.filePath, _indent: indent })
  }
}
```

```vue
<el-table :data="fileTreeFlat" row-key="rowKey" @selection-change="handleSelection">
  <el-table-column type="selection" width="40" />
  <el-table-column label="文件名" min-width="300">
    <template #default="{ row }">
      <span v-if="row._isExecDir" style="font-weight: bold; color: #409eff">
        <el-icon><FolderOpened /></el-icon> {{ row.name }}
      </span>
      <span v-else-if="row.directory" :style="{ paddingLeft: '16px' }">
        <el-icon><Folder /></el-icon> {{ row.name }}/
      </span>
      <span v-else :style="{ paddingLeft: '32px' }">
        <el-icon><Document /></el-icon> {{ row.name }}
      </span>
    </template>
  </el-table-column>
  <el-table-column label="大小" width="100">
    <template #default="{ row }">
      {{ row.directory ? '-' : formatSize(row.size) }}
    </template>
  </el-table-column>
</el-table>
```

## Frontend: Download Handlers

```typescript
// Single file or batch
const handleBatchDownload = async () => {
  const paths = selectedFiles.value.map(f => f.filePath).filter(Boolean)
  const blob = await batchDownload(projectId, paths) as any
  triggerBlobDownload(blob, project.name + '_files.zip')
}

// Download all
const handleDownloadAll = async () => {
  const blob = await downloadAll(projectId) as any
  triggerBlobDownload(blob, project.name + '_all.zip')
}
```

## Pitfalls
- File tree DTO uses `filePath` (absolute) for download, `path` (relative) for display
- Batch download body is `List<String>` (file paths), not `List<Long>` (file IDs)
- Size limit: 200MB default for batch download
- Empty tree: show `<el-empty>` with helpful message
