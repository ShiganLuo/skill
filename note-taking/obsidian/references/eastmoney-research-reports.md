# 东方财富证券研报中心数据采集

## 数据源

东方财富证券研报中心: https://data.eastmoney.com/report/industry.jshtml

页面是 SPA，数据通过 JS 渲染，但底层 API 可用。

## API 端点

```
GET https://reportapi.eastmoney.com/report/list
```

### 参数
- `industryCode`: 行业代码（`*` 为全部，具体行业如 `SW801` 为医药生物）
- `pageNo`: 页码
- `pageSize`: 每页条数
- `beginTime`: 开始日期 `YYYY-MM-DD`
- `endTime`: 结束日期 `YYYY-MM-DD`
- `qType`: 报告类型（0=行业研报）
- `code`: `*` 为全部

### 返回字段
- `title`: 报告标题
- `orgSName`: 发布机构名称
- `publishDate`: 发布日期
- `infoCode`: 报告ID（拼接URL用）
- `industryName`: 所属行业

### 报告链接构造
```
https://data.eastmoney.com/report/info/{infoCode}.html
```

## 浏览器方式提取（推荐）

API 在无 cookie 环境下可能返回空结果，更可靠的方式是浏览器渲染后 JS 提取：

1. `browser_navigate` 到行业研报页面
2. `browser_console` 执行 JS 提取表格数据：
```javascript
const rows = document.querySelectorAll('table tbody tr');
const results = [];
rows.forEach(row => {
  const cells = row.querySelectorAll('td');
  if (cells.length >= 10) {
    results.push({
      industry: cells[1]?.textContent?.trim(),
      title: cells[4]?.textContent?.trim(),
      org: cells[7]?.textContent?.trim(),
      date: cells[9]?.textContent?.trim()
    });
  }
});
```

3. 点击行业筛选按钮切换子行业：
```javascript
const links = document.querySelectorAll('a');
for (const link of links) {
  if (link.textContent.trim() === '目标行业名') {
    link.click();
    break;
  }
}
```

## 生物医药相关行业分类

东方财富的行业分类中，生物/医药相关包括：
- **生物制品** — 创新药、生物药、CXO、基因检测
- **化学制药** — 化学创新药、仿制药
- **医疗器械** — 设备、IVD、高值耗材
- **医疗服务** — 医院、CRO、AI医疗
- **医药商业** — 流通、医保、投融资

## 反爬注意

- `curl` 直接请求 API 可能返回空数据
- 搜索引擎（Google/百度/Bing）在无代理环境下会触发 CAPTCHA
- DuckDuckGo HTML 版可能超时
- **推荐方案**: 浏览器渲染 + JS 提取，或直接访问东方财富数据中心

## 其他报告来源（备选）

| 来源 | URL | 特点 |
|------|-----|------|
| 前瞻产业研究院 | bg.qianzhan.com | 行业深度报告，部分免费 |
| 艾瑞咨询 | iresearch.com.cn | 互联网/AI为主，生物较少 |
| 头豹研究院 | leadleo.com | 行业概览报告 |
| 蛋壳研究院 | (微信公众号) | 医疗健康行业 |
| 动脉网 | vcbeat.net | 医疗健康创投 |
