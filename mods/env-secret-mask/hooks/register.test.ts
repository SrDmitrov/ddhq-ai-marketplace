import { expect, test } from 'claude-code/testing'

test('writes carrying a mask are refused', async ($, on) => {
  on('tool.call', () => ({ result: { type: 'create' } as never }))
  const masked = await $.tool.call({ tool: 'Write', file_path: '/tmp/.env', content: 'KEY=sk-a…[REDACTED:30]…0XyZ' })
  expect(masked.deny ?? masked.text).toContain('masked secret')

  const clean = await $.tool.call({ tool: 'Write', file_path: '/tmp/a.txt', content: 'hello' })
  expect(clean.deny).toBeUndefined()
})
