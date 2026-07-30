import { chromium } from 'playwright';

const BASE_URL = 'http://localhost:8877';
const errors = [];
const failed = [];
const checks = [];

function record(name, pass, detail = {}) {
  checks.push({ name, pass, ...detail });
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
page.on('pageerror', (err) => errors.push(`PAGEERROR: ${err.message}`));
page.on('requestfailed', (req) => failed.push(`${req.url()} :: ${req.failure()?.errorText || 'failed'}`));

await page.goto(`${BASE_URL}/fastpheno-dashboard.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForFunction(() => typeof weatherEcccPIK !== 'undefined' && weatherEcccPIK.length > 0, { timeout: 30000 });

record('home page visible', await page.locator('#home-page').isVisible());
record('domain cards count', (await page.locator('.domain-card').count()) === 3, { count: await page.locator('.domain-card').count() });
record('available entities', (await page.locator('#domain-home-grid .entity-card.available').count()) === 4, {
  count: await page.locator('#domain-home-grid .entity-card.available').count(),
});

await page.goto(`${BASE_URL}/fastpheno-dashboard.html#environmental/climate`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(1000);
record('hash opens climate view', await page.locator('#sensor-view').isVisible()
  && (await page.locator('#sensor-view-header').textContent())?.includes('Climate'));
record('weather source control visible', await page.locator('#weather-source-control').isVisible());
record('weather detail panel visible', await page.locator('#weather-detail').isVisible());

const detailBefore = await page.locator('#weather-detail-title').textContent();
await page.selectOption('#weather-source', 'daymet');
await page.waitForTimeout(800);
const detailAfter = await page.locator('#weather-detail-title').textContent();
const daymetMetrics = await page.evaluate(() => WEATHER_METRICS_DAYMET.length);
record('daymet source switch updates detail', detailAfter !== detailBefore || detailAfter?.includes('Daymet') || daymetMetrics > 0, { detailBefore: detailBefore?.trim(), detailAfter: detailAfter?.trim() });
record('daymet data loaded', await page.evaluate(() => weatherDaymetPIK.length > 0 && weatherDaymetPIN.length > 0), {
  daymetPIK: await page.evaluate(() => weatherDaymetPIK.length),
  daymetPIN: await page.evaluate(() => weatherDaymetPIN.length),
});

await page.locator('#back-to-home').click();
await page.waitForTimeout(300);
await page.locator('#domain-home-grid [data-domain="ground"][data-entity="fluorescence"]').click();
await page.waitForTimeout(800);
record('fluorescence opens', await page.locator('#fluorescence-section').isVisible(), {
  header: (await page.locator('#sensor-view-header').textContent())?.trim(),
});
await page.locator('#fluor-add-series').click();
await page.waitForTimeout(600);
record('fluorescence series rows', (await page.locator('#fluorescence-table .tabulator-row').count()) > 0, {
  rows: await page.locator('#fluorescence-table .tabulator-row').count(),
  count: (await page.locator('#fluorescence-count').textContent())?.trim(),
});

await page.locator('#back-to-home').click();
await page.waitForTimeout(300);
await page.locator('#domain-home-grid [data-domain="ground"][data-entity="wp"]').click();
await page.waitForTimeout(800);
await page.locator('#wp-add-series').click();
await page.waitForTimeout(600);
const wpCount = (await page.locator('#wp-count').textContent())?.trim();
record('wp opens with data', (await page.locator('#wp-section').isVisible()) && (wpCount?.includes('wp') || wpCount?.includes('water') || (await page.locator('#summary-table .tabulator-row').count()) > 0), { wpCount });
record('wp table renders', (await page.locator('#summary-table .tabulator-row').count()) > 0, {
  rows: await page.locator('#summary-table .tabulator-row').count(),
});

await page.goto(`${BASE_URL}/fastpheno-dashboard.html#uav/lidar`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(500);
record('blank entity panel', await page.locator('#blank-section').isVisible());

await page.locator('#back-to-home').click();
await page.waitForTimeout(300);
record('back to home', await page.locator('#home-page').isVisible());

const passed = checks.filter((c) => c.pass).length;
const result = {
  baseUrl: BASE_URL,
  summary: `${passed}/${checks.length} checks passed`,
  checks,
  errors,
  failed: failed.filter((f) => !f.includes('127.0.0.1:7386')),
};
console.log(JSON.stringify(result, null, 2));
await browser.close();
process.exitCode = passed === checks.length ? 0 : 1;
