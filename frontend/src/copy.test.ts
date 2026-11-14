import { expect, test } from 'vitest'
import { copy } from './copy'
test('copy avoids restricted phrases', () => { expect(JSON.stringify(copy)).not.toMatch(/diagnos|you have|(increase|decrease|change) (your )?(dose|medication)/i) })
test('footer is exact', () => { expect(copy.footer).toBe('Tremor Lab is a tracking tool, not a medical device. Discuss results with your doctor.') })
