# Export Functionality Pattern (Excel + PPT)

## Overview
Generate downloadable Excel (.xlsx) and PPT (.pptx) reports from Spring Boot backend.

## Dependencies (pom.xml)

```xml
<!-- Apache POI (Excel + PPT export) -->
<dependency>
    <groupId>org.apache.poi</groupId>
    <artifactId>poi-ooxml</artifactId>
    <version>5.2.5</version>
</dependency>
```

**Note**: poi-ooxml is heavy (~10MB+ with transitive deps). If only Excel needed, consider easyexcel (Alibaba, lighter). For both Excel + PPT, poi-ooxml is the only option.

## Service Pattern

```java
@Service
public class ProjectExportServiceImpl implements ProjectExportService {

    private final ProjectMapper projectMapper;
    private final DataFileMapper dataFileMapper;
    private final PipelineMapper pipelineMapper;

    // Excel generation
    public ByteArrayOutputStream generateExcel(Long projectId) {
        Project project = projectMapper.selectById(projectId);
        if (project == null) throw new RuntimeException("项目不存在");

        try (XSSFWorkbook wb = new XSSFWorkbook();
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            
            // Sheet1: Project info
            Sheet infoSheet = wb.createSheet("项目信息");
            CellStyle headerStyle = createHeaderStyle(wb);
            int row = 0;
            row = writeRow(infoSheet, row, new String[]{"字段", "值"}, headerStyle);
            writeRow(infoSheet, row++, new String[]{"项目名称", project.getName()});
            // ... more rows
            
            // Sheet2: Data files
            Sheet fileSheet = wb.createSheet("数据文件");
            // ... table with headers and data rows
            
            wb.write(out);
            return out;
        } catch (IOException e) {
            throw new RuntimeException("生成Excel失败", e);
        }
    }

    // PPT generation
    public ByteArrayOutputStream generatePpt(Long projectId) {
        try (XMLSlideShow ppt = new XMLSlideShow();
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            ppt.setPageSize(new java.awt.Dimension(960, 540));
            
            // Slide 1: Title
            XSLFSlideLayout titleLayout = ppt.getSlideMasters().get(0)
                .getLayout(SlideLayout.TITLE);
            XSLFSlide slide1 = ppt.createSlide(titleLayout);
            slide1.getPlaceholder(0).setText("项目名称");
            slide1.getPlaceholder(1).setText("副标题");
            
            // Slide 2: Content
            XSLFSlideLayout contentLayout = ppt.getSlideMasters().get(0)
                .getLayout(SlideLayout.TITLE_AND_CONTENT);
            XSLFSlide slide2 = ppt.createSlide(contentLayout);
            slide2.getPlaceholder(0).setText("标题");
            slide2.getPlaceholder(1).setText("内容");
            
            ppt.write(out);
            return out;
        } catch (IOException e) {
            throw new RuntimeException("生成PPT失败", e);
        }
    }

    // Helper methods
    private CellStyle createHeaderStyle(Workbook wb) {
        CellStyle style = wb.createCellStyle();
        Font font = wb.createFont();
        font.setBold(true);
        style.setFont(font);
        style.setFillForegroundColor(IndexedColors.GREY_25_PERCENT.getIndex());
        style.setFillPattern(FillPatternType.SOLID_FOREGROUND);
        return style;
    }

    private int writeRow(Sheet sheet, int rowNum, String[] values, CellStyle style) {
        Row row = sheet.createRow(rowNum);
        for (int i = 0; i < values.length; i++) {
            Cell cell = row.createCell(i);
            cell.setCellValue(values[i] != null ? values[i] : "");
            if (style != null) cell.setCellStyle(style);
        }
        return rowNum + 1;
    }
}
```

## Controller Pattern

```java
@GetMapping("/{id}/export/excel")
public void exportExcel(@PathVariable Long id, HttpServletResponse response) throws IOException {
    ByteArrayOutputStream baos = projectExportService.generateExcel(id);
    Project project = projectService.getProjectById(id);
    String filename = (project != null ? project.getName() : "project") + "_report.xlsx";
    
    response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    response.setHeader("Content-Disposition", 
        "attachment; filename=\"" + URLEncoder.encode(filename, "UTF-8") + "\"");
    response.setContentLength(baos.size());
    baos.writeTo(response.getOutputStream());
    response.getOutputStream().flush();
}

@GetMapping("/{id}/export/ppt")
public void exportPpt(@PathVariable Long id, HttpServletResponse response) throws IOException {
    ByteArrayOutputStream baos = projectExportService.generatePpt(id);
    // ... same pattern as Excel
    response.setContentType("application/vnd.openxmlformats-officedocument.presentationml.presentation");
    // ...
}
```

## Frontend Pattern

```typescript
// API
export function exportExcel(projectId: number) {
  return http.get(`/api/admin/projects/${projectId}/export/excel`, { responseType: 'blob' })
}

// Download handler
const triggerBlobDownload = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

const handleExportExcel = async () => {
  loading.value = true
  try {
    const blob = await exportExcel(projectId) as any
    triggerBlobDownload(blob, project.name + '_report.xlsx')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  } finally {
    loading.value = false
  }
}
```

## Pitfalls
- POI class names: `XSLFSlideLayout` (not `XSLFSlideSlideLayout`)
- `response.setContentType()` must match the file format
- Use `URLEncoder.encode(filename, "UTF-8")` for Content-Disposition
- Frontend must use `responseType: 'blob'` in axios config
