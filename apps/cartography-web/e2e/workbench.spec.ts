import { createHash } from 'node:crypto';
import { expect, test, type Page } from '@playwright/test';

const SNAPSHOT = 'cartography-system-graph-source-backed-2026-07-27';
const DESKTOP_SCREENSHOT_DIGEST = '71c29a0685d1b4d4b37059324531c4d92f75ce1e1e91144ff6ec9db4978bd628';
const MOBILE_SCREENSHOT_DIGEST = '902b465b5f9ba567f5e5b62642cf7a9fb34697288fe2e66bc8434024baa96eef';

function workbenchUrl(
  view: 'mindmap' | 'lineage' | 'outline' = 'mindmap',
  values: Record<string, string> = {},
): string {
  const params = new URLSearchParams({
    view,
    root: 'notion-global-working-memory',
    depth: '4',
    snapshot: SNAPSHOT,
    ...values,
  });
  return `/?${params.toString()}`;
}

async function expectScreenshotDigest(page: Page, name: string, expectedDigest: string): Promise<void> {
  const image = await page.screenshot({ fullPage: true, animations: 'disabled', caret: 'hide' });
  await test.info().attach(name, { body: image, contentType: 'image/png' });
  const digest = createHash('sha256').update(image).digest('hex');
  expect(digest, `${name} SHA-256 screenshot regression`).toBe(expectedDigest);
}

async function attachEvidenceScreenshot(page: Page, name: string): Promise<void> {
  const image = await page.screenshot({ fullPage: true, animations: 'disabled', caret: 'hide' });
  await test.info().attach(name, { body: image, contentType: 'image/png' });
}

test('keeps Mind Map, Lineage, and Outline inside one URL-backed shell', async ({ page }) => {
  await page.goto(workbenchUrl());
  await expect(page.getByText('AIOS Cartography')).toBeVisible();
  await expect(page.getByTestId('gpu-shell')).toBeVisible();
  const status = page.getByLabel('Workbench status');
  await expect(status).toHaveAttribute('data-renderer-backend', /webgpu|webgl2/);
  await expect(status).toHaveAttribute('data-runtime-state', /ready|fallback/);
  await expect(page.getByText('STALE')).toBeVisible();
  await expect(page.getByText('PARTIAL')).toBeVisible();

  await page.getByRole('button', { name: 'Lineage' }).click();
  await expect(page).toHaveURL(/view=lineage/);
  await page.goBack();
  await expect(page).toHaveURL(/view=mindmap/);

  await page.getByRole('button', { name: 'Outline' }).click();
  await expect(page.getByTestId('outline-view')).toBeVisible();
  await expect(page).toHaveURL(/view=outline/);
});

test('shows resolved cross-source coverage without rendering gap placeholders', async ({ page }) => {
  await page.goto(workbenchUrl('outline'));
  const coverage = page.getByLabel('System graph coverage');
  await expect(coverage).toContainText('8/8 domains');
  await expect(coverage).toContainText('41');
  await expect(coverage).toContainText('3');
  await expect(page.getByText('IMPLEMENTATION', { exact: true })).toBeVisible();
  await expect(
    page.getByTestId('outline-view').getByText('neohack2023/AIOS-Tools', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Registry row-level graph expansion', { exact: true })).toHaveCount(0);
});

test('search, selection, inspector, root focus, and history restore workspace state', async ({ page }) => {
  await page.goto(workbenchUrl('outline'));
  const search = page.getByRole('searchbox', { name: 'Search graph' });
  await search.fill('Capability Registry');
  await page.getByRole('button', { name: /Capability Registry/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Capability Registry' })).toBeVisible();
  await expect(page).toHaveURL(/selected=notion-capability-registry/);

  await page.getByRole('button', { name: 'Focus as root' }).click();
  await expect(page).toHaveURL(/root=notion-capability-registry/);
  await page.goBack();
  await expect(page).toHaveURL(/root=notion-global-working-memory/);

  await search.fill('apps/cartography-web');
  await page.getByRole('button', { name: /apps\/cartography-web/ }).first().click();
  await expect(page.getByRole('heading', { name: 'apps/cartography-web/' })).toBeVisible();
  await expect(page.getByText('implementation', { exact: true })).toBeVisible();
});

test('inspects the checked-in Observatory projection without exposing raw runtime data', async ({ page }) => {
  await page.goto(workbenchUrl('outline', { selected: 'notion-observability-index' }));
  const panel = page.getByTestId('observatory-panel');

  await expect(panel).toBeVisible();
  await expect(panel.getByText('CHECKED-IN FIXTURE', { exact: true })).toBeVisible();
  await expect(panel.getByText('READ ONLY', { exact: true })).toBeVisible();
  await expect(panel.getByText('INSUFFICIENT', { exact: true }).first()).toBeVisible();
  await expect(panel.getByText('L0->L1', { exact: true }).first()).toBeVisible();

  await panel.getByLabel('Section').selectOption('identities');
  await panel.getByRole('searchbox', { name: 'Filter metadata' }).fill('receipt');
  await panel.getByRole('button', { name: /Receipt Id/ }).click();
  await expect(panel.getByText('identities.receipt_id', { exact: true })).toBeVisible();
  await expect(panel.getByText(/^cr_[0-9a-f]{64}$/).last()).toBeVisible();
  await expect(panel.getByText('context_expansion_decision', { exact: true })).toHaveCount(0);
  await expect(panel.getByText('cognition_receipt', { exact: true })).toHaveCount(0);

  await attachEvidenceScreenshot(page, 'observatory-panel-desktop.png');
});

test('keeps the Observatory fixture inspectable in mobile portrait focus mode', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(workbenchUrl('outline', { selected: 'notion-observability-index' }));
  const panel = page.getByTestId('observatory-panel');

  await expect(panel).toBeVisible();
  await expect(panel.getByRole('searchbox', { name: 'Filter metadata' })).toBeVisible();
  await expect(panel.getByText('Source content, raw events, raw receipts', { exact: false })).toBeVisible();
  await attachEvidenceScreenshot(page, 'observatory-panel-mobile.png');
});

test('surfaces graphics context loss instead of leaving a blank viewport', async ({ page }) => {
  await page.goto(workbenchUrl());
  await expect(page.getByTestId('gpu-shell')).toBeVisible();
  const status = page.getByLabel('Workbench status');
  await expect(status).toHaveAttribute('data-renderer-backend', /webgpu|webgl2/);
  await page.locator('canvas').evaluate((canvas) =>
    canvas.dispatchEvent(new Event('webglcontextlost', { cancelable: true })),
  );
  await expect(status).toHaveAttribute('data-runtime-state', 'context-lost');
  await expect(page.getByText('CONTEXT LOST', { exact: true })).toBeVisible();
});

test('desktop application shell screenshot remains stable', async ({ page }) => {
  await page.goto(workbenchUrl('outline', { selected: 'notion-cartography-contract' }));
  await expect(page.getByTestId('outline-view')).toBeVisible();
  await expectScreenshotDigest(page, 'workbench-outline-desktop.png', DESKTOP_SCREENSHOT_DIGEST);
});

test('mobile portrait focus mode screenshot remains stable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(workbenchUrl('outline', { selected: 'notion-cartography-contract' }));
  await expect(page.getByText('AIOS System Cartography Engine Contract', { exact: true }).last()).toBeVisible();
  await expectScreenshotDigest(page, 'workbench-mobile-focus.png', MOBILE_SCREENSHOT_DIGEST);
});
