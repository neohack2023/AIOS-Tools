import { expect, test } from '@playwright/test';

const DEFAULT_URL = '/?view=mindmap&root=notion-global-working-memory&depth=4&snapshot=cartography-workbench-source-backed-2026-07-27';

test('keeps Mind Map, Lineage, and Outline inside one URL-backed shell', async ({ page }) => {
  await page.goto(DEFAULT_URL);
  await expect(page.getByText('AIOS Cartography')).toBeVisible();
  await expect(page.getByTestId('gpu-shell')).toBeVisible();
  await expect(page.getByText(/WEBGPU|WEBGL2/)).toBeVisible();
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

test('search, selection, inspector, root focus, and history restore workspace state', async ({ page }) => {
  await page.goto(`${DEFAULT_URL}&view=outline`);
  const search = page.getByRole('searchbox', { name: 'Search graph' });
  await search.fill('Capability Registry');
  await page.getByRole('button', { name: /Capability Registry/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Capability Registry' })).toBeVisible();
  await expect(page).toHaveURL(/selected=notion-capability-registry/);

  await page.getByRole('button', { name: 'Focus as root' }).click();
  await expect(page).toHaveURL(/root=notion-capability-registry/);
  await page.goBack();
  await expect(page).toHaveURL(/root=notion-global-working-memory/);
});

test('surfaces graphics context loss instead of leaving a blank viewport', async ({ page }) => {
  await page.goto(DEFAULT_URL);
  await expect(page.getByTestId('gpu-shell')).toBeVisible();
  await page.locator('canvas').dispatchEvent('webglcontextlost');
  await expect(page.getByText('CONTEXT LOST')).toBeVisible();
});

test('desktop application shell screenshot remains stable', async ({ page }) => {
  await page.goto(`${DEFAULT_URL}&view=outline&selected=notion-cartography-contract`);
  await expect(page.getByTestId('outline-view')).toBeVisible();
  await expect(page).toHaveScreenshot('workbench-outline-desktop.png', { fullPage: true });
});

test('mobile portrait focus mode screenshot remains stable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${DEFAULT_URL}&selected=notion-cartography-contract`);
  await expect(page.getByText('AIOS System Cartography Engine Contract', { exact: true }).last()).toBeVisible();
  await expect(page).toHaveScreenshot('workbench-mobile-focus.png', { fullPage: true });
});
