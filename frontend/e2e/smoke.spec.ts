import { expect, test } from '@playwright/test'
test('home, navigation and simulator work without a backend', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.locator('canvas')).toBeVisible()
  await expect.poll(() => page.locator('canvas').evaluate(canvas => {
    const context = (canvas as HTMLCanvasElement).getContext('2d')!
    const pixels = context.getImageData(0, 0, (canvas as HTMLCanvasElement).width, (canvas as HTMLCanvasElement).height).data
    let count = 0
    for (let i = 0; i < pixels.length; i += 4) if (pixels[i] < 100 && pixels[i + 1] > 100 && pixels[i + 1] < 160 && pixels[i + 3] > 150) count++
    return count
  })).toBeGreaterThan(50)
  await page.getByRole('link', { name: 'Explore your check' }).click()
  await expect(page.getByRole('heading', { name: 'Get to know your check' })).toBeVisible()
  await page.getByRole('link', { name: 'Simulator', exact: true }).click()
  const slider = page.getByRole('slider', { name: 'Tremor frequency (Hz)' })
  await slider.fill('10')
  await expect(page.locator('output').first()).toHaveText('10')
  await page.getByRole('button', { name: 'Reset simulator' }).click()
  await expect(slider).toHaveValue('5')
})
test('mobile layout fits the viewport and navigation opens', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Toggle navigation' }).click()
  await page.getByRole('link', { name: 'Your trends', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your trends', exact: true })).toBeVisible()
})
