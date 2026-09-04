# RSS Feed Implementation Pattern (Spring Boot + Vue3)

## Overview
Add RSS 2.0 feed support to a blog. No external RSS library needed — use Java's built-in DOM API.

## Backend

### 1. Service (RssService.java)
```java
@Service
public class RssService {
    // Generate RSS 2.0 XML using javax.xml DOM API
    // - Get blog settings for Channel info (title, description)
    // - Query latest published articles (is_deleted=0, status=1)
    // - Build RSS XML with DocumentBuilderFactory
    // - Return as String with MediaType.APPLICATION_XML_VALUE
}
```

Key points:
- Use `DocumentBuilderFactory` + `DocumentBuilder` to create XML
- RSS 2.0 requires: `<rss version="2.0">`, `<channel>`, `<item>` elements
- Add `xmlns:atom` namespace for self-referencing link
- Format dates with `EEE, dd MMM yyyy HH:mm:ss Z` (RFC 822)
- Limit to 20 most recent articles

### 2. Controller (RssController.java)
```java
@RestController
@RequestMapping("/api/front")
public class RssController {
    @GetMapping(value = "/rss", produces = MediaType.APPLICATION_XML_VALUE)
    public String getRss(HttpServletRequest request) {
        String baseUrl = getBaseUrl(request); // scheme://host:port
        return rssService.generateRss(baseUrl);
    }
}
```

Key points:
- Return `String` (not `ApiResponse`) — RSS is raw XML
- Use `produces = MediaType.APPLICATION_XML_VALUE`
- Detect baseUrl from HttpServletRequest (handles proxy/CDN)
- Place under `/api/front/**` to inherit whitelist (no auth needed)

### 3. Mapper (ArticleMapper)
```xml
<select id="getRecentArticlesForRss" resultType="java.util.HashMap">
    SELECT id, title, summary, created_at
    FROM articles
    WHERE is_deleted = 0 AND status = 1
    ORDER BY created_at DESC
    LIMIT #{limit}
</select>
```

Use `HashMap` result type — no need for a dedicated DTO for RSS.

### 4. Security Config
The endpoint `/api/front/rss` should already be in the whitelist if `/api/front/**` is whitelisted. No changes needed.

## Frontend

### 1. HTML Head (index.html)
```html
<link rel="alternate" type="application/rss+xml" title="RSS 订阅" href="/api/front/rss">
```
This enables RSS auto-discovery in browsers and feed readers.

### 2. Navigation Menu
```vue
<el-menu-item @click="openRss">
  <i class="iconfont icon-rss"></i> RSS
</el-menu-item>
```

```typescript
const openRss = () => {
  window.open(`${window.location.origin}/api/front/rss`, '_blank');
};
```

## RSS 2.0 Structure Reference
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Blog Title</title>
    <link>https://example.com</link>
    <description>Blog description</description>
    <language>zh-CN</language>
    <lastBuildDate>RFC822 date</lastBuildDate>
    <atom:link href="https://example.com/api/front/rss" rel="self" type="application/rss+xml"/>
    <item>
      <title>Article Title</title>
      <link>https://example.com/article/1</link>
      <guid>https://example.com/article/1</guid>
      <description>Article summary (HTML allowed)</description>
      <pubDate>RFC822 date</pubDate>
    </item>
  </channel>
</rss>
```

## Common Pitfalls
- Don't wrap RSS response in `ApiResponse` — RSS readers expect raw XML
- Don't require authentication — RSS feeds must be publicly accessible
- Use `created_at` not `published_at` if published_at may be null
- Filter `is_deleted=0 AND status=1` to only include published articles
- The `<guid>` should be unique and stable (use article URL)
