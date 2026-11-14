import { expect, test } from '@playwright/test'

test('mode selection slides without remounting and connections celebrate once', async ({ page }) => {
  await page.goto('/check/connect')
  const mode = page.getByRole('group', { name: 'Data source' })
  await mode.evaluate(element => element.setAttribute('data-motion-instance', 'original'))
  await page.getByRole('button', { name: 'Sensor mode', exact: true }).click()
  await expect(mode).toHaveAttribute('data-motion-instance', 'original')
  await expect.poll(() => mode.evaluate(element => new DOMMatrixReadOnly(getComputedStyle(element, '::before').transform).m41)).toBeGreaterThan(40)
  await page.getByRole('button', { name: 'Demo mode', exact: true }).click()
  await expect.poll(() => mode.evaluate(element => Math.round(new DOMMatrixReadOnly(getComputedStyle(element, '::before').transform).m41))).toBe(0)
  const next = page.locator('.test-continue')
  const before = await next.boundingBox()
  await page.clock.install()
  await page.getByRole('button', { name: 'Connect Devices', exact: true }).click()
  await page.clock.runFor(450)
  await expect(page.locator('.device-row.is-detected')).toHaveCount(1)
  await expect(next).toBeDisabled()
  await expect(page.locator('.confetti-burst')).toHaveCount(0)
  await page.clock.runFor(400)
  await expect(page.locator('.device-row.is-detected')).toHaveCount(2)
  await expect(next).toBeDisabled()
  await page.clock.runFor(400)
  await expect(page.locator('.device-row.is-detected')).toHaveCount(3)
  await expect(next).toBeEnabled()
  await expect(page.locator('.confetti-piece')).toHaveCount(36)
  await expect(page.locator('.device-status-symbol')).toHaveClass(/is-celebrating/)
  const after = await next.boundingBox()
  expect(after?.x).toBe(before?.x)
  expect(after?.y).toBe(before?.y)
  expect(after?.height).toBe(before?.height)
  await page.clock.runFor(1700)
  await expect(page.locator('.confetti-burst')).toHaveCount(0)
  await page.reload()
  await expect(next).toBeEnabled()
  await expect(page.locator('.confetti-burst')).toHaveCount(0)
  await expect(page.locator('.device-status-symbol')).not.toHaveClass(/is-celebrating/)
})

test('reduced motion preserves ready states without movement or confetti', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/check/connect')
  await expect(page.locator('.check-mode')).toHaveCSS('position', 'relative')
  expect(await page.locator('.check-mode').evaluate(element => getComputedStyle(element, '::before').transitionDuration)).toBe('0s')
  await page.clock.install()
  await page.getByRole('button', { name: 'Connect Devices', exact: true }).click()
  await page.clock.runFor(1300)
  await expect(page.locator('.test-continue')).toBeEnabled()
  await expect(page.locator('.confetti-burst')).toBeHidden()
  await expect(page.locator('.device-status-symbol')).toHaveCSS('animation-name', 'none')
  await expect(page.getByRole('heading', { name: 'Devices are ready', exact: true })).toBeVisible()
})

test('buttons darken with a sweep, cards enlarge subtly, and header history preserves progress', async ({ page }) => {
  await page.goto('/')
  const button = page.getByRole('link', { name: 'Start a movement check', exact: true })
  const background = await button.evaluate(element => getComputedStyle(element).backgroundImage)
  await button.hover()
  const sweep = await button.evaluate(async element => {
    const transition = element.getAnimations({ subtree: true }).find(animation => animation instanceof CSSTransition && animation.transitionProperty === 'transform')
    if (!transition) throw new Error('No hover sweep transition started')
    transition.pause()
    transition.currentTime = 120
    await new Promise(requestAnimationFrame)
    return {
      scale: new DOMMatrixReadOnly(getComputedStyle(element, '::after').transform).m11,
      origin: getComputedStyle(element, '::after').transformOrigin,
      background: getComputedStyle(element).backgroundImage,
    }
  })
  expect(sweep.scale).toBeGreaterThan(0)
  expect(sweep.scale).toBeLessThan(1)
  expect(sweep.origin.startsWith('0px')).toBe(true)
  expect(sweep.background).toBe(background)
  await expect.poll(() => page.locator('.operate-card').evaluate(element => new DOMMatrixReadOnly(getComputedStyle(element).transform).m11)).toBeCloseTo(1.01, 2)
  await page.getByRole('link', { name: 'Test history', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your check history', exact: true })).toBeVisible()
  await page.goto('/check/connect')
  await expect(page.getByRole('link', { name: 'Back to home', exact: true })).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  await page.clock.install()
  await page.getByRole('button', { name: 'Connect Devices', exact: true }).click()
  await page.clock.runFor(1300)
  await page.getByRole('link', { name: 'Test history', exact: true }).click()
  await page.getByRole('link', { name: 'Home', exact: true }).first().click()
  await page.getByRole('link', { name: 'Resume your check', exact: true }).click()
  await expect(page).toHaveURL(/\/check\/rest$/)
})

test('switches share a design and page transitions respect reduced motion', async ({ page }) => {
  await page.goto('/check/connect')
  const connectionStyle = await page.locator('.check-mode').evaluate(element => {
    const group = getComputedStyle(element)
    const option = getComputedStyle(element.querySelector('button')!)
    return { height: group.height, padding: group.padding, border: group.border, radius: group.borderRadius, background: group.backgroundColor, font: option.fontSize }
  })
  await page.evaluate(() => {
    const original = Element.prototype.animate
    const observed: Animation[] = []
    Reflect.set(window, 'observedPageAnimations', observed)
    Element.prototype.animate = function (...args: Parameters<typeof original>) {
      const animation = original.apply(this, args)
      const recorded = Reflect.get(window, 'observedPageAnimations') as Animation[]
      recorded.push(animation)
      return animation
    }
  })
  await page.getByRole('link', { name: 'Test history', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your check history', exact: true })).toBeVisible()
  const historyStyle = await page.locator('.history-period').evaluate(element => {
    const group = getComputedStyle(element)
    const option = getComputedStyle(element.querySelector('button')!)
    return { height: group.height, padding: group.padding, border: group.border, radius: group.borderRadius, background: group.backgroundColor, font: option.fontSize }
  })
  expect(historyStyle).toEqual(connectionStyle)
  const transition = await page.evaluate(() => {
    const animations = Reflect.get(window, 'observedPageAnimations') as Animation[]
    const entry = animations.find(animation => animation.id === 'page-enter')
    return { duration: entry?.effect?.getTiming().duration, frames: (entry?.effect as KeyframeEffect | null)?.getKeyframes() }
  })
  expect(transition.duration).toBe(260)
  expect(transition.frames?.[0].opacity).toBe('0')
  expect(transition.frames?.[1].opacity).toBe('1')
  const count = await page.locator('tbody tr').count()
  await page.getByRole('button', { name: '7 days', exact: true }).focus()
  await page.keyboard.press('Space')
  await expect(page.getByRole('button', { name: '7 days', exact: true })).toHaveAttribute('aria-pressed', 'true')
  expect(await page.locator('tbody tr').count()).toBeLessThan(count)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.evaluate(() => Reflect.set(window, 'observedPageAnimations', []))
  await page.getByRole('link', { name: 'Home', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'Your movement check', exact: true })).toBeVisible()
  const starts = await page.evaluate(() => (Reflect.get(window, 'observedPageAnimations') as Animation[]).filter(animation => animation.id === 'page-enter').length)
  expect(starts).toBe(0)
  await expect(page.getByText('Demo workspace', { exact: true })).toHaveCount(0)
})
