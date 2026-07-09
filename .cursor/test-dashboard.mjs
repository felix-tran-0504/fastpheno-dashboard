import { chromium } from 'playwright';

const errors = [];
const failed = [];
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
page.on('pageerror', (err) => errors.push(`PAGEERROR: ${err.message}`));
page.on('requestfailed', (req) => failed.push(`${req.url()} :: ${req.failure()?.errorText || 'failed'}`));

await page.goto('http://localhost:8765/fastpheno-dashboard.html', { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(2500);

const result = {
  statsLabel: await page.locator('#stats-panel .label').first().textContent().catch(() => null),
  recordsCount: await page.locator('#data-records-count').textContent().catch(() => ''),
  weatherRows: await page.locator('#weather-table .tabulator-row').count(),
  fluorRows: await page.locator('#fluorescence-table .tabulator-row').count(),
  reflRows: await page.locator('#reflectance-table .tabulator-row').count(),
  visibleCharts: await page.locator('.chart-box:not(.is-hidden)').count(),
  loadingPanels: await page.locator('.loading').count(),
  errors,
  failed,
};
console.log(JSON.stringify(result, null, 2));
await browser.close();
