import { expect, test } from 'vitest'
import { RingBuf } from './ringbuf'
import { nextBackoff } from '../api/useSensorStream'
test('keeps the latest samples in timestamp order', () => {
  const buf = new RingBuf(10, 1)
  for (let i = 0; i < 15; i++) buf.push(i, [i])
  const times: number[] = []
  buf.forEach(t => times.push(t))
  expect(times).toEqual([5, 6, 7, 8, 9, 10, 11, 12, 13, 14])
  expect(buf.last()?.t).toBe(14)
  buf.clear()
  expect(buf.size).toBe(0)
  expect(buf.last()).toBeUndefined()
})
test('reconnect delay grows and is capped', () => { expect([0,1,2,3,4,10].map(nextBackoff)).toEqual([500,1000,2000,4000,5000,5000]) })
