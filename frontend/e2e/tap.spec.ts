import { expect, test, type Page } from '@playwright/test'
import type { TapDataIn } from '../src/api/types'
test.use({ launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] } })
async function openTap(page: Page) {
  await page.goto('/check/connect')
  await page.evaluate(() => {
    const records = Object.fromEntries(['connect', 'rest', 'posture', 'reach'].map(step => [step, { runs: step === 'reach' ? 3 : 1, seconds: 30 }]))
    sessionStorage.setItem('tremor-check-v2', JSON.stringify({ mode: 'sensor', checkId: 42, hand: 'right', records }))
  })
  await page.goto('/check/tap')
}
async function mockDetector(page: Page) {
  await page.route('**/src/tap/handLandmarker.ts', route => route.fulfill({ contentType: 'application/javascript', body: `
    export async function createHandLandmarker() { return {
      detectForVideo(video, now) { return { landmarks: [Array.from({length:21}, (_,i) => ({x: i / 30, y: .5 + .2 * Math.sin(now / 50)}))] } }, close() {}
    } }
  ` }))
}
test('real local model loads, missing hands fail safely, and camera stops', async ({ page }) => {
  test.setTimeout(45000)
  const assets: string[] = []
  page.on('request', request => { if (request.url().includes('/mediapipe/')) assets.push(request.url()) })
  await page.route('**/api/checks/42/tests', route => route.fulfill({ json: { test_id: 10 } }))
  let payload: TapDataIn | undefined
  await page.route('**/api/tests/10/tap-data', route => {
    payload = route.request().postDataJSON()
    return route.fulfill({ json: { test_id: 10, status: 'failed', fail_reason: 'no_taps_detected', result: null } })
  })
  await openTap(page)
  await page.getByRole('button', { name: 'Start left hand', exact: true }).click()
  await expect(page.getByText('No taps were found.', { exact: false }).first()).toBeVisible({ timeout: 35000 })
  expect(payload!.frames.length).toBeGreaterThan(5)
  expect(payload!.frames.every(frame => frame.lm === null)).toBe(true)
  expect(assets.some(url => url.endsWith('hand_landmarker.task'))).toBe(true)
  expect(assets.some(url => url.endsWith('.wasm'))).toBe(true)
  expect(assets.every(url => url.startsWith('http://localhost:5174/'))).toBe(true)
  await expect(page.locator('.test-continue')).toBeDisabled()
  expect(await page.locator('video').evaluate(el => (el as HTMLVideoElement).srcObject)).toBeNull()
  await expect(page.getByRole('button', { name: 'Skip this step' })).toBeEnabled()
})
test('both hands submit separately and left hand progress survives refresh', async ({ page }) => {
  await mockDetector(page)
  await page.clock.install()
  const hands: string[] = []
  const payloads: TapDataIn[] = []
  await page.route('**/api/checks/42/tests', route => {
    hands.push(route.request().postDataJSON().hand)
    return route.fulfill({ json: { test_id: hands.length } })
  })
  await page.route('**/api/tests/*/tap-data', route => {
    payloads.push(route.request().postDataJSON())
    return route.fulfill({ json: { test_id: hands.length, status: 'done', fail_reason: null, result: null } })
  })
  await openTap(page)
  for (const hand of ['left', 'right']) {
    await page.getByRole('button', { name: `Start ${hand} hand`, exact: true }).click()
    await expect(page.locator('.test-next-status')).toContainText('Get ready')
    await page.clock.runFor(13500)
    await expect.poll(() => payloads.length).toBe(hand === 'left' ? 1 : 2)
    if (hand === 'left') {
      await expect(page.getByRole('button', { name: 'Start right hand', exact: true })).toBeEnabled()
      await expect(page.locator('.test-continue')).toBeDisabled()
      await page.reload()
    }
  }
  expect(hands).toEqual(['left', 'right'])
  for (const payload of payloads) {
    expect(payload.frames.length).toBeGreaterThan(0)
    expect(payload.frames.every(frame => frame.lm?.length === 4)).toBe(true)
    expect(payload.frames.every((frame, i) => i === 0 || frame.t_ms > payload.frames[i - 1].t_ms)).toBe(true)
  }
  await expect(page.locator('.test-continue')).toBeEnabled()
})
test('camera denied leaves skip available and creates no backend test', async ({ page }) => {
  await page.addInitScript(() => { navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('Denied', 'NotAllowedError') } })
  let starts = 0
  await page.route('**/api/checks/42/tests', route => { starts++; return route.abort() })
  await openTap(page)
  await page.getByRole('button', { name: 'Start left hand', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Camera unavailable')
  expect(starts).toBe(0)
  await page.getByRole('button', { name: 'Skip this step' }).click()
  await expect(page.locator('.test-continue')).toBeEnabled()
})
test('leaving tap releases the camera and closes the unfinished backend test', async ({ page }) => {
  await mockDetector(page)
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
    navigator.mediaDevices.getUserMedia = async constraints => {
      const stream = await original(constraints)
      Reflect.set(window, 'tapTestTracks', stream.getTracks())
      return stream
    }
  })
  await page.route('**/api/checks/42/tests', route => route.fulfill({ json: { test_id: 10 } }))
  let payload: TapDataIn | undefined
  await page.route('**/api/tests/10/tap-data', route => {
    payload = route.request().postDataJSON()
    return route.fulfill({ json: { test_id: 10, status: 'failed', fail_reason: 'no_taps_detected', result: null } })
  })
  await openTap(page)
  await page.getByRole('button', { name: 'Start left hand', exact: true }).click()
  await expect(page.locator('.test-next-status')).toContainText('Get ready')
  await page.getByRole('link', { name: 'Back to home', exact: true }).click()
  await expect.poll(() => payload).toEqual({ frames: [] })
  expect(await page.evaluate(() => (Reflect.get(window, 'tapTestTracks') as MediaStreamTrack[]).every(track => track.readyState === 'ended'))).toBe(true)
})
