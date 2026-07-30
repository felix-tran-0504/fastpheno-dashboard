import { chromium } from 'playwright';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import path from 'path';

const TEST_PORT = Number(process.env.TEST_PORT) || 8877;
const BASE_URL = `http://localhost:${TEST_PORT}`;
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function waitForServer(maxMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try {
      const res = await fetch(`${BASE_URL}/fastpheno-dashboard.html`);
      if (res.ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`Test server not ready on port ${TEST_PORT}`);
}

async function ensureTestServer() {
  try {
    const res = await fetch(`${BASE_URL}/fastpheno-dashboard.html`);
    if (res.ok) {
      console.error(`Using existing test server: ${BASE_URL}`);
      return null;
    }
  } catch {}

  const server = spawn('python3', ['-m', 'http.server', String(TEST_PORT)], {
    cwd: ROOT,
    stdio: 'ignore',
  });
  await waitForServer();
  console.error(`Started test server: ${BASE_URL}`);
  return server;
}

const server = await ensureTestServer();

try {
  const errors = [];
  const failed = [];
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', (err) => errors.push(`PAGEERROR: ${err.message}`));
  page.on('requestfailed', (req) => failed.push(`${req.url()} :: ${req.failure()?.errorText || 'failed'}`));

  await page.goto(`${BASE_URL}/fastpheno-dashboard.html`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForFunction(() => typeof weatherEcccPIK !== 'undefined' && weatherEcccPIK.length > 0, { timeout: 30000 });

  const homeVisible = await page.locator('#home-page').isVisible();
  const sensorViewHidden = await page.locator('#sensor-view').isHidden();

  const sensorEntity = {
    weather: '[data-domain="environmental"][data-entity="climate"]',
    fluorescence: '[data-domain="ground"][data-entity="fluorescence"]',
    reflectance: '[data-domain="ground"][data-entity="leaf_reflectance"]',
    wp: '[data-domain="ground"][data-entity="wp"]',
  };

  async function testSensor(sensorId, tableSelector, countSelector, { singleDayWeather = false } = {}) {
    if (!(await page.locator('#home-page').isVisible())) {
      await page.locator('#back-to-home').click();
      await page.waitForTimeout(300);
    }
    await page.locator(`#domain-home-grid ${sensorEntity[sensorId]}`).click();
    await page.waitForTimeout(1200);
    if (sensorId === 'fluorescence') {
      await page.locator('#fluor-add-series').click();
      await page.waitForTimeout(500);
    } else if (sensorId === 'reflectance') {
      await page.locator('#refl-add-series').click();
      await page.waitForTimeout(500);
    } else if (sensorId === 'wp') {
      await page.locator('#wp-add-series').click();
      await page.waitForTimeout(500);
    }
    const header = await page.locator('#sensor-view-header').textContent();
    const countText = countSelector ? await page.locator(countSelector).textContent().catch(() => '') : '';
    const rows = tableSelector ? await page.locator(`${tableSelector} .tabulator-row`).count() : 0;
    const chartBoxId = sensorId === 'weather' ? 'weather-chart-box'
      : sensorId === 'fluorescence' ? 'fluorescence-chart-box'
      : sensorId === 'reflectance' ? 'reflectance-chart-box'
      : 'wp-chart-box';
    const chartVisible = sensorId === 'weather'
      ? (await page.locator('#weather-chart-box').isVisible() || await page.locator('#weather-detail').isVisible())
      : await page.locator(`#${chartBoxId}`).isVisible();
    const sectionVisible = await page.locator(`#${sensorId === 'wp' ? 'wp' : sensorId}-section`).isVisible();
    const result = { sensorId, header: header?.trim(), countText: countText?.trim(), rows, chartVisible, sectionVisible };
    if (singleDayWeather) {
      result.detailVisible = await page.locator('#weather-detail').isVisible();
      result.tableHidden = await page.locator('#weather-table').isHidden();
      result.countHidden = await page.locator('#weather-count').isHidden();
      result.metricControlHidden = await page.locator('#weather-metric-control').isHidden();
    }
    return result;
  }

  const sensors = [];
  sensors.push(await testSensor('weather', null, null, { singleDayWeather: true }));
  for (const [sensorId, tableSelector, countSelector] of [
    ['fluorescence', '#fluorescence-table', '#fluorescence-count'],
    ['reflectance', '#reflectance-table', '#reflectance-count'],
    ['wp', '#summary-table', '#wp-count'],
  ]) {
    sensors.push(await testSensor(sensorId, tableSelector, countSelector));
  }

  await page.locator('#back-to-home').click();
  await page.waitForTimeout(300);
  const backHome = await page.locator('#home-page').isVisible();

  // Weather date range sanity: To must be strictly after From
  await page.locator('#domain-home-grid [data-domain="environmental"][data-entity="climate"]').click();
  await page.waitForTimeout(800);
  await page.locator('#weather-mode-toggle button[data-mode="range"]').click();
  await page.waitForTimeout(400);
  const weatherMetricControlVisible = await page.locator('#weather-metric-control').isVisible();
  const weatherVariableMetrics = await page.evaluate(() => {
    const variable = getVariableWeatherMetricsForCurrentData().map(m => m.field);
    const all = getWeatherMetrics().map(m => m.field);
    return { variable, constant: all.filter(f => !variable.includes(f)) };
  });

  // PIN + ECCC: constant metadata must be excluded from filter and single-day detail
  await page.locator('#weather-mode-toggle button[data-mode="single"]').click();
  await page.waitForTimeout(300);
  await page.locator('#site-filter').selectOption('PIN');
  await page.locator('#weather-source').selectOption('eccc');
  await page.waitForTimeout(400);
  const pinEcccMetrics = await page.evaluate(() => {
    const variable = getVariableWeatherMetricsForCurrentData().map(m => m.field);
    const all = getWeatherMetrics().map(m => m.field);
    return { variable, excluded: all.filter(f => !variable.includes(f)) };
  });
  const pinEcccSingleDayDetail = await page.evaluate(() => {
    const metrics = getVariableWeatherMetricsForCurrentData().map(m => m.field);
    return { detailMetricFields: metrics };
  });
  const expectedPinExcluded = [
    'lat', 'lon', 'elev', 'n_stations', 'mean_distance', 'site_lat', 'site_lon', 'vpd',
  ];
  const pinExclusionOk = expectedPinExcluded.every(f => pinEcccMetrics.excluded.includes(f))
    && expectedPinExcluded.every(f => !pinEcccSingleDayDetail.detailMetricFields.includes(f));

  await page.locator('#weather-mode-toggle button[data-mode="range"]').click();
  await page.waitForTimeout(400);
  const weatherRangeTable = await page.evaluate(() => {
    const cols = weatherTable?.getColumns?.() || [];
    return {
      columnCount: cols.length,
      downloadVisible: !document.getElementById('weather-table-footer').classList.contains('is-hidden'),
    };
  });
  const weatherRangeRows = await page.locator('#weather-table .tabulator-row').count();

  const weatherDateBounds = await page.evaluate(() => {
    const rows = getWeatherBaseRows();
    return { first: rows[0].date, last: rows[rows.length - 1].date };
  });
  const midIdx = Math.floor(
    (await page.evaluate(() => getWeatherBaseRows().length)) / 2
  );
  const midDate = await page.evaluate((idx) => getWeatherBaseRows()[idx].date, midIdx);
  await page.locator('#weather-from-date').fill(midDate);
  await page.locator('#weather-from-date').dispatchEvent('change');
  await page.waitForTimeout(300);
  const toAfterFromChange = await page.locator('#weather-to-date').inputValue();
  const fromSnapsToForward = toAfterFromChange > midDate;

  await page.locator('#weather-to-date').fill(weatherDateBounds.first);
  await page.locator('#weather-from-date').fill(weatherDateBounds.last);
  await page.locator('#weather-from-date').dispatchEvent('change');
  await page.waitForTimeout(300);
  const fromAfterInvalid = await page.locator('#weather-from-date').inputValue();
  const toAfterInvalid = await page.locator('#weather-to-date').inputValue();
  const fromAfterToChange = await page.evaluate(() => {
    document.getElementById('weather-to-date').value = getWeatherDateBounds().first;
    document.getElementById('weather-from-date').value = getWeatherDateBounds().last;
    enforceWeatherDateRange('to');
    return {
      from: document.getElementById('weather-from-date').value,
      to: document.getElementById('weather-to-date').value,
      toMin: document.getElementById('weather-to-date').min,
    };
  });
  const toMinAfterFrom = fromAfterToChange.toMin > fromAfterToChange.from;
  const rangeOrderValid = fromAfterToChange.from < fromAfterToChange.to;

  const result = {
    testPort: TEST_PORT,
    baseUrl: BASE_URL,
    homeVisible,
    sensorViewHidden,
    dataLoaded: await page.evaluate(() => ({
      weatherEcccPIK: weatherEcccPIK.length,
      weatherEcccPIN: weatherEcccPIN.length,
      fluorescence: fluorescence.length,
      reflectance: reflectance.length,
      predawnWP: predawnWP.length,
    })),
    sensors,
    backHome,
    weatherDateRange: {
      bounds: weatherDateBounds,
      fromSnapsToForward,
      fromAfterInvalid,
      toAfterInvalid,
      fromAfterToChange,
      toMinAfterFrom,
      rangeOrderValid,
    },
    weatherMetricControlVisible,
    weatherVariableMetrics,
    weatherRangeTable,
    weatherRangeRows,
    pinEcccMetrics,
    pinEcccSingleDayDetail,
    pinExclusionOk,
    errors,
    failed: failed.filter((f) => !f.includes('127.0.0.1:7386')),
  };
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
} finally {
  if (server) server.kill();
}
