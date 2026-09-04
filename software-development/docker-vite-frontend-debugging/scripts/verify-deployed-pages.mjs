// Verify deployed Vue3 pages via headless Chrome + Puppeteer
// Usage: node scripts/verify-deployed-pages.mjs <url1> [url2] ...
// Captures: API response codes, console errors, page content

import puppeteer from 'puppeteer-core';

const urls = process.argv.slice(2);
if (!urls.length) {
  console.error('Usage: node verify-deployed-pages.mjs <url1> [url2] ...');
  process.exit(1);
}

const browser = await puppeteer.launch({
  executablePath: '/usr/bin/google-chrome',
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--ignore-certificate-errors']
});

for (const url of urls) {
  const page = await browser.newPage();
  const errors = [];
  const apiCalls = [];

  page.on('response', resp => {
    if (resp.url().includes('/api/')) {
      apiCalls.push(`${resp.status()} ${resp.request().method()} ${new URL(resp.url()).pathname}`);
    }
  });
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', err => errors.push(`PAGE_ERROR: ${err.message}`));

  console.log(`\n=== ${url} ===`);
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 20000 });
  console.log('Final URL:', page.url());
  console.log('Title:', await page.title());
  const body = await page.evaluate(() => document.body.innerText.substring(0, 300));
  console.log('Body:', body);

  if (apiCalls.length) {
    console.log('API calls:');
    apiCalls.forEach(c => console.log('  ', c));
  }
  if (errors.length) {
    console.log('Errors:');
    errors.forEach(e => console.log('  ', e));
  }

  await page.close();
}

await browser.close();
