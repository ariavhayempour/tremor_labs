import { afterEach, expect, test, vi } from 'vitest'
import { request } from './client'
afterEach(() => vi.unstubAllGlobals())
test('preserves API failure status and reason', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: 'test_active' }), { status: 409 })))
  await expect(request('/api/checks')).rejects.toMatchObject({ status: 409, error: 'test_active' })
})
test('204 responses resolve without parsing a body', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
  await expect(request('/api/led')).resolves.toBeUndefined()
})
