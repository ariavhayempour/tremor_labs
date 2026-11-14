import { expect, test } from '@playwright/test'
test('five-step check gates progression, supports pause and survives refresh', async ({ page }) => {
  await page.clock.install()
  await page.goto('/check/connect')
  await expect(page).toHaveURL(/\/check\/connect$/)
  const next = page.locator('.test-continue')
  await expect(next).toBeDisabled()
  await page.getByRole('button', { name: 'Connect Devices', exact: true }).click()
  await page.clock.runFor(1300)
  await expect(next).toBeEnabled()
  await next.click()
  await expect(page).toHaveURL(/\/check\/rest$/)
  await expect(next).toBeDisabled()
  await page.getByRole('button', { name: 'Start the Test', exact: true }).click()
  await page.clock.runFor(10000)
  await page.getByRole('button', { name: 'Pause test', exact: true }).click()
  const frozen = await page.getByRole('progressbar').getAttribute('value')
  await page.clock.runFor(5000)
  await expect(page.getByRole('progressbar')).toHaveAttribute('value', frozen!)
  await expect(next).toBeDisabled()
  await page.getByRole('button', { name: 'Resume test', exact: true }).click()
  await page.clock.runFor(20500)
  await expect(next).toBeEnabled()
  await expect(next).toHaveClass(/is-ready/)
  await page.reload()
  await expect(next).toBeEnabled()
  await expect.poll(() => page.locator('canvas').evaluate(canvas => {
    const pixels = (canvas as HTMLCanvasElement).getContext('2d')!.getImageData(0, 0, (canvas as HTMLCanvasElement).width, (canvas as HTMLCanvasElement).height).data
    let ink = 0
    for (let i = 0; i < pixels.length; i += 4) if (pixels[i] < 80 && pixels[i + 3] > 150) ink++
    return ink
  })).toBeGreaterThan(50)
  await next.click()
  await expect(page).toHaveURL(/\/check\/posture$/)
  await expect(page.locator('.height-guide')).toBeVisible()
  await page.getByRole('button', { name: 'Start the Test', exact: true }).click()
  await page.clock.runFor(30500)
  await next.click()
  await expect(page).toHaveURL(/\/check\/reach$/)
  for (let i = 1; i <= 3; i++) {
    await expect(next).toBeDisabled()
    await page.getByRole('button', { name: `Start attempt ${i}`, exact: true }).click()
    await page.clock.runFor(6500)
    if (i < 3) await expect(next).toBeDisabled()
  }
  await next.click()
  await expect(page).toHaveURL(/\/check\/tap$/)
  await page.getByRole('button', { name: 'Start left hand', exact: true }).click()
  await page.clock.runFor(10500)
  await expect(next).toBeDisabled()
  await page.getByRole('button', { name: 'Start right hand', exact: true }).click()
  await page.clock.runFor(10500)
  await expect(next).toBeEnabled()
  await next.click()
  await expect(page.getByRole('heading', { name: 'Your check is complete' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => {
    const saved = JSON.parse(localStorage.getItem('tremor-history-v1') ?? '[]') as { source: string }[]
    return saved.filter(record => record.source === 'demo').length
  })).toBe(1)
  await page.getByRole('link', { name: 'See the result', exact: true }).click()
  await expect(page).toHaveURL(/\/check\/results$/)
  await expect(page.getByRole('heading', { name: 'Your check results', exact: true })).toBeVisible()
  await expect(page.locator('.result-card')).toHaveCount(4)
  await expect(page.locator('.result-card canvas')).toHaveCount(4)
  await expect(page.getByText('2 hands completed', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.locator('.result-card canvas')).toHaveCount(4)
  await page.getByRole('link', { name: 'Back to summary', exact: true }).click()
  await expect(page.getByRole('link', { name: 'See the result', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Start a new check' }).click()
  await expect(page).toHaveURL(/\/check\/connect$/)
  await expect(page.locator('.test-continue')).toBeDisabled()
})
test('direct links cannot bypass unfinished steps and sensor errors keep Continue disabled', async ({ page }) => {
  await page.goto('/check/tap')
  await expect(page).toHaveURL(/\/check\/connect$/)
  await page.getByRole('button', { name: 'Sensor mode', exact: true }).click()
  await page.route('http://localhost:8000/api/health', route => route.abort())
  await page.getByRole('button', { name: 'Connect Devices', exact: true }).click()
  await expect(page.locator('.test-visualization-footer')).toContainText('Connection interrupted')
  await expect(page.locator('.test-continue')).toBeDisabled()
  await page.getByRole('button', { name: 'Demo mode', exact: true }).click()
  await expect(page.locator('.test-visualization-footer')).toContainText('Simulated signals')
})
test('five-step mobile layout fits and retains instructions and bottom action', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/check/connect')
  await expect(page.getByRole('heading', { name: 'Connect to Devices', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect(page.locator('.check-tab')).toHaveCount(5)
  await page.locator('.test-continue').scrollIntoViewIfNeeded()
  await expect(page.locator('.test-continue')).toBeVisible()
})
test('all five test pages fit a laptop viewport without scrolling or clipping', async ({ page }) => {
  const steps = ['connect', 'rest', 'posture', 'reach', 'tap']
  for (const size of [{ width: 1366, height: 768 }, { width: 1280, height: 720 }]) {
    await page.setViewportSize(size)
    for (const [index, step] of steps.entries()) {
      await page.goto('/check/connect')
      await page.evaluate(({ steps, index }) => {
        const records = Object.fromEntries(steps.slice(0, index).map(step => [step, { runs: step === 'reach' ? 3 : 1, seconds: 30 }]))
        sessionStorage.setItem('tremor-check-v2', JSON.stringify({ mode: 'demo', records }))
      }, { steps, index })
      await page.goto(`/check/${step}`)
      const layout = await page.evaluate(() => {
        const items = ['.instruction-panel', '.test-exit', '.test-visualization', '.test-continue', '.test-footer'].map(selector => {
          const el = document.querySelector(selector)!
          const rect = el.getBoundingClientRect()
          return { selector, top: rect.top, bottom: rect.bottom, clipped: el.scrollHeight > el.clientHeight + 1 }
        })
        return { pageHeight: document.documentElement.scrollHeight, pageWidth: document.documentElement.scrollWidth, items }
      })
      expect(layout.pageHeight, `${step} at ${size.width}`).toBeLessThanOrEqual(size.height)
      expect(layout.pageWidth).toBeLessThanOrEqual(size.width)
      for (const item of layout.items) {
        expect(item.top, item.selector).toBeGreaterThanOrEqual(0)
        expect(item.bottom, item.selector).toBeLessThanOrEqual(size.height)
        expect(item.clipped, item.selector).toBe(false)
      }
    }
  }
})

test('completion page and both actions fit without scrolling on desktop and mobile', async ({ page }) => {
  await page.goto('/check/results')
  await expect(page).toHaveURL(/\/check\/connect$/)
  await page.evaluate(() => {
    const records = Object.fromEntries(['connect', 'rest', 'posture', 'reach', 'tap'].map(step => [step, { runs: step === 'reach' ? 3 : step === 'tap' ? 2 : 1, seconds: 30 }]))
    sessionStorage.setItem('tremor-check-v2', JSON.stringify({ mode: 'demo', records }))
  })
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1280, height: 650 }, { width: 390, height: 844 }, { width: 390, height: 740 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/check/complete')
    await expect(page.getByRole('link', { name: 'See the result', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start a new check', exact: true })).toBeVisible()
    const layout = await page.evaluate(() => ({
      height: document.documentElement.scrollHeight,
      width: document.documentElement.scrollWidth,
      items: ['.check-summary h1', '.check-summary ol', '.summary-actions', '.check-summary footer'].map(selector => {
        const element = document.querySelector(selector)!
        const rect = element.getBoundingClientRect()
        return { top: rect.top, bottom: rect.bottom, clipped: element.scrollHeight > element.clientHeight + 1 }
      }),
    }))
    expect(layout.height).toBeLessThanOrEqual(viewport.height)
    expect(layout.width).toBeLessThanOrEqual(viewport.width)
    for (const item of layout.items) {
      expect(item.top).toBeGreaterThanOrEqual(0)
      expect(item.bottom).toBeLessThanOrEqual(viewport.height)
      expect(item.clipped).toBe(false)
    }
  }
})

for (const review of ['complete', 'results']) {
  test(`sensor ${review} keeps the backend results route`, async ({ page }) => {
    await page.route('**/api/checks/42', route => route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }))
    await page.goto('/check/connect')
    await page.evaluate(() => {
      const records = Object.fromEntries(['connect', 'rest', 'posture', 'reach', 'tap'].map(step => [step, { runs: step === 'reach' ? 3 : step === 'tap' ? 2 : 1, seconds: 30 }]))
      sessionStorage.setItem('tremor-check-v2', JSON.stringify({ mode: 'sensor', checkId: 42, hand: 'right', records }))
    })
    const backendResult = page.waitForResponse(response => response.url().endsWith('/api/checks/42'))
    await page.goto(`/check/${review}`)
    await backendResult
    await expect(page).toHaveURL(/\/results\/42$/)
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.locator('.check-results')).toHaveCount(0)
  })
}
