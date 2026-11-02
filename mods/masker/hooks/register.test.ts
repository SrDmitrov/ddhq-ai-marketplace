import { expect, test } from 'claude-code/testing'

test('writes carrying a mask are refused', async ($, on) => {
  on('tool.call', () => ({ result: { type: 'create' } as never }))
  const masked = await $.tool.call({ tool: 'Write', file_path: '/tmp/.env', content: 'KEY=sk-a…[REDACTED:30]…0XyZ' })
  expect(masked.deny ?? masked.text).toContain('masked secret')

  const clean = await $.tool.call({ tool: 'Write', file_path: '/tmp/a.txt', content: 'hello' })
  expect(clean.deny).toBeUndefined()
})

test('a mentioned file holding a secret is refused, a clean one read', async ($, on) => {
  const files: Record<string, string> = {
    '/p/.env': `GITHUB_TOKEN=ghp_${'aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2eF4hJ6'}`,
    '/p/notes.md': 'auth: basic, token: true',
  }
  on('fs.read', ($, e) => {
    if (!(e.path in files)) throw new Error('missing')
    return { value: files[e.path] }
  })
  on('prompt.mention', () => ({ type: 'file' as const }))

  const secret = await $.prompt.mention({ mention: '.env', path: '/p/.env' })
  expect(secret.deny).toContain('github-pat')
  const clean = await $.prompt.mention({ mention: 'notes.md', path: '/p/notes.md' })
  expect(clean.type).toBe('file')
  const unreadable = await $.prompt.mention({ mention: 'gone', path: '/p/gone' })
  expect(unreadable.deny).toContain('could not check')
})
