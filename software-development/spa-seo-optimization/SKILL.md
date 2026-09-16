---
name: spa-seo-optimization
description: "Use when adding SEO to SPA+backend projects."
---

# SPA SEO Optimization

Add search-engine-friendly features to Single Page Application (Vue3/React) with backend API (Spring Boot/Node).

## Why SPAs Need Extra Work

SPAs serve a single `index.html` for all routes. Crawlers CAN execute JS (Googlebot), but social previews (WeChat, Telegram, Twitter cards) cannot — OG tags must be in the initial HTML. Also, `robots.txt` and `sitemap.xml` must be served as plain text/XML, not as the SPA fallback HTML.

## Step 1: robots.txt + sitemap.xml Backend Endpoints

Create backend endpoints that return plain text / XML:

- `GET /robots.txt` — `User-agent: * / Allow: / / Sitemap: https://domain/sitemap.xml`
- `GET /sitemap.xml` — query all published content from DB, generate `<urlset>` XML

**Spring Security**: add both paths to whitelist in ALL `application-*.yml`:
```yaml
security:
  jwt:
    whitelist:
      - /robots.txt
      - /sitemap.xml
```

**X-Forwarded headers**: enable in `application-prod.yml`:
```yaml
server:
  forward-headers-strategy: native
```
Without this, `request.getScheme()` returns `http` even when the client connected via HTTPS through a reverse proxy.

## Step 2: Nginx SPA Fallback Exception

In the frontend nginx config, `try_files $uri /index.html` catches ALL unmatched paths including `/robots.txt`. Add exact-match location blocks BEFORE `try_files`:

```nginx
location = /robots.txt {
    proxy_pass http://backend:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
}
location = /sitemap.xml {
    proxy_pass http://backend:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
}
location / {
    root /usr/share/nginx/html;
    try_files $uri $uri/ /index.html;
}
```

## Step 3: Dynamic Meta Tags (Vue3 + @vueuse/head)

Install: `pnpm add @vueuse/head` (or `npm install @vueuse/head`)

Setup in `main.ts`:
```ts
import { createHead } from '@vueuse/head'
const head = createHead()
app.use(head)
```

In page components, use `useHead()` with `computed()` for reactive meta:
```ts
import { useHead } from '@vueuse/head'
import { computed } from 'vue'

useHead({
  title: computed(() => data.title ? `${data.title} - SiteName` : 'SiteName'),
  meta: computed(() => [
    { name: 'description', content: description.value },
    { property: 'og:title', content: data.title },
    { property: 'og:description', content: description.value },
    { property: 'og:image', content: data.coverImage },
    { property: 'og:type', content: 'article' },
    { name: 'twitter:card', content: data.coverImage ? 'summary_large_image' : 'summary' },
  ]),
  link: computed(() => [
    { rel: 'canonical', href: window.location.origin + '/path?id=' + data.id }
  ]),
  script: computed(() => [{
    type: 'application/ld+json',
    children: JSON.stringify({
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": data.title,
      "description": description.value,
      "author": { "@type": "Person", "name": data.authorName },
      "datePublished": data.createdAt,
      "dateModified": data.updatedAt || data.createdAt,
    })
  }])
})
```

## Step 4: HTML lang Attribute

In `index.html`: `<html lang="zh-CN">` (or appropriate language code). Empty `lang=""` hurts SEO ranking for language-specific searches.

## Multi-Layer Nginx Proxy Pitfall

When there's a chain: client → nginx-proxy (HTTPS) → frontend-nginx (HTTP) → backend (HTTP):

- `$scheme` in the inner nginx reflects the INNER connection (always `http`)
- `$http_x_forwarded_proto` preserves the ORIGINAL client protocol (`https`)
- Always use `$http_x_forwarded_proto` in inner proxy blocks

**After container recreation**: nginx-proxy caches old container DNS. External requests return default nginx welcome page. Fix: `docker exec nginx-proxy nginx -s reload`

## Verification Checklist

```bash
# robots.txt returns plain text
curl https://domain/robots.txt

# sitemap.xml returns valid XML with https:// URLs
curl https://domain/sitemap.xml

# Article page has OG tags in source (view-source or curl)
curl -s https://domain/article?id=1 | grep 'og:title'

# Validate JSON-LD: https://search.google.com/test/rich-results
# Submit sitemap: Google Search Console -> Sitemaps
```
