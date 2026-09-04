---
name: career-research
description: >-
  Research job postings on Chinese company career portals AND build/improve resumes from wiki/project files.
  Find campus/social recruitment positions, extract structured data from SPA career pages, verify positions are real with links.
  Also covers resume building - extract PDF resume, scan wiki for gaps, synthesize improved version.
trigger: User asks to find jobs, research campus recruitment (校招), search positions on company career pages, analyze job market for specific roles, OR create/improve/update their resume/CV from existing materials and wiki.
---

# Career Research: Chinese Company Career Portals

Research real job postings on Chinese company career portals. Output verified positions with direct links.

## Workflow

1. **Go directly to company career pages** — do NOT use delegate_task (times out on heavy SPA sites) or DuckDuckGo curl (unreliable for Chinese queries). Use `browser_navigate` directly.
2. **Use `browser_console` to extract structured data** — NOT `browser_snapshot` (truncates at ~80 elements). Run JS to extract job titles, IDs, locations, descriptions, and detail-page URLs from the DOM.
3. **Try multiple search keywords** — "生物信息" may return 0 results while "医疗" returns 268. Always try at least 3 variants.
4. **Verify each position** — click through to detail page or extract real `href` attributes. Never fabricate URLs.
5. **Check graduation period** — Chinese campus recruitment explicitly states 毕业时间 (graduation window). Verify the target graduation date falls within range.

## Company Career Page Directory

### Tech Companies (校园招聘 / Campus Recruitment)
| Company | URL | Notes |
|---------|-----|-------|
| 字节跳动 ByteDance | https://jobs.bytedance.com/campus | Best structured. Has 2027届校招. Search: `?keywords=XXX`. Detail URL pattern: `/campus/position/{numeric_id}/detail` |
| 腾讯 Tencent | https://join.qq.com/ | 毕业时间窗口较窄. 青云计划 = research talent program |
| 阿里巴巴 Alibaba | https://talent.alibaba.com/campus/position-list?lang=zh | 阿里星计划, limited positions |
| 华为 Huawei | https://career.huawei.com/reccampportal/portal5/campus-recruitment.html | Bilingual page, search often returns 0 for Chinese keywords |
| 美团 Meituan | https://zhaopin.meituan.com/web/campus | URL search doesn't work, must use in-page search box |
| 百度 Baidu | https://talent.baidu.com/campus | Page may fail to load via browser |

### Biotech / Genomics Companies
| Company | URL | Notes |
|---------|-----|-------|
| 华大基因 BGI | https://genomics.zhiye.com/campus/jobs | Beisen (北森) platform. Job IDs: JXXXXX. No direct detail URLs (SPA modal) |
| 诺禾致源 Novogene | https://novogene.zhiye.com/Campus | Beisen platform. May show 0 positions off-season |
| 药明康德 WuXi | https://careers.wuxiapptec.com/ | May be blocked/unreachable from China |

### Platform Notes
- **Beisen (北森) sites** (`*.zhiye.com`): Job listings are SPA modals, no direct detail URL. Use the search page URL as reference. Extract job IDs (JXXXXX) via `browser_console`.
- **ByteDance**: Best URL structure. Detail pages accessible via direct URL. ByteIntern positions explicitly state graduation period.
- **Tencent**: 毕业时间 in homepage banner. 应届生 vs 实习生 have different windows.

## browser_console Extraction Patterns

### Extract job links from ByteDance
```javascript
(() => {
  const links = document.querySelectorAll('a[href*="detail"]');
  return JSON.stringify(Array.from(links).map(a => ({
    text: a.innerText.substring(0, 150),
    href: a.href
  })).filter(r => r.text.length > 5));
})()
```

### Extract full job text from any SPA
```javascript
(() => {
  const main = document.querySelector('main') || document.body;
  return main.innerText.substring(0, 5000);
})()
```

### Find Beisen job links
```javascript
(() => {
  const allLinks = document.querySelectorAll('a');
  return JSON.stringify(Array.from(allLinks)
    .filter(a => a.innerText.includes('J'))
    .map(a => ({text: a.innerText.substring(0, 100), href: a.href})));
})()
```

## Pitfalls

1. **delegate_task with browser toolset times out** on heavy SPA career sites (600s timeout, 25-46 API calls wasted). Always use browser tools directly.
2. **DuckDuckGo HTML search** (`html.duckduckgo.com/html/?q=...`) returns empty for most Chinese job-related queries. Do not rely on it.
3. **browser_snapshot truncates** at ~80 elements, hiding job listings. Use `browser_console` with `innerText` extraction instead.
4. **URL-based search** doesn't work on Meituan (`/web/campus/search?keyword=XXX` → 404). Must use in-page search input.
5. **BGI careers page** at `/careers/` returns 404. Real portal is at `genomics.zhiye.com` (found via footer "加入我们" link href).
6. **Alibaba** defaults to English (`lang=en`). Must append `?lang=zh` for Chinese.
7. **Campus recruitment timing**: 2027届秋招 typically opens August-September 2026. Some companies (ByteDance) open early; others (Tencent, Alibaba) may still show 2026 positions in early August.

## Search Keyword Strategy

For bioinformatics/medical AI positions, try these keywords in order:
1. "生物信息" — most specific, may return 0 on tech company sites
2. "医疗" — broader, returns many results on ByteDance (268 positions)
3. "基因" — for genomics-specific roles
4. "算法" — for algorithm engineer positions (very broad)
5. "健康" — catches health-tech positions

## Resume Building

For creating or improving resumes from existing materials and wiki content, see `references/resume-building-workflow.md`.

## See Also

- `references/company-findings-2026-08.md` — Detailed findings per company from August 2026 session
- `references/resume-building-workflow.md` — Resume extraction, gap analysis, and improvement workflow