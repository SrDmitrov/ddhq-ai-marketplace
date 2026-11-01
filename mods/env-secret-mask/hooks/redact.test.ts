import { expect, test } from 'claude-code/testing'
import { isHighEntropy, mask, parseEnv, pickSecrets, redact, redactBlock } from './redact'

const TOKEN = 'sk-ant-api03-AbCdEfGh1234567890XyZ'

test('mask keeps head and tail only', () => {
  expect(mask(TOKEN)).toBe(`sk-a…[REDACTED:${TOKEN.length}]…0XyZ`)
  expect(mask('hunter2pw')).toBe('hu…[REDACTED:9]…pw')
  expect(mask('short')).toBe('[REDACTED:5]')
})

test('picks secrets by name or entropy, skips ordinary vars', () => {
  const env = parseEnv(
    ['HOME=/Users/me', 'PATH=/usr/bin:/bin', 'PWD=/tmp/project', `MY_API_KEY=${TOKEN}`,
     'DB_PASSWORD=hunter2pw', 'RANDOM_BLOB=Zx9#qL2!vR8@mT4$wK7%', 'SHELL=/bin/zsh'].join('\0'),
  )
  expect(pickSecrets(env)).toEqual([TOKEN, 'Zx9#qL2!vR8@mT4$wK7%', 'hunter2pw'])
  expect(isHighEntropy('/usr/local/bin/something-long')).toBe(false)
})

test('redacts exact values anywhere', () => {
  const out = redact(`curl -H "Bearer ${TOKEN}" done`, [TOKEN])
  expect(out.includes(TOKEN)).toBe(false)
  expect(out).toContain('sk-a…[REDACTED:')
})

test('redacts NAME=value pairs in .env, yaml and json', () => {
  const text = [
    'STRIPE_SECRET_KEY=sk_live_abcdef123456',
    'export GITHUB_TOKEN="ghp_0123456789abcdef"',
    'password: s3cr3t-value',
    '{"apiKey": "AKIAABCDEFGHIJKL"}',
    'DEBUG=true',
  ].join('\n')
  const out = redact(text, [])
  for (const leaked of ['sk_live_abcdef123456', 'ghp_0123456789abcdef', 's3cr3t-value', 'AKIAABCDEFGHIJKL']) {
    expect(out.includes(leaked)).toBe(false)
  }
  expect(out).toContain('DEBUG=true')
  expect(out).toContain('export GITHUB_TOKEN="ghp_…[REDACTED:20]…cdef"')
})

test('masks tool_result content, string and nested blocks', () => {
  const asString = redactBlock({ type: 'tool_result', tool_use_id: 't1', content: `out ${TOKEN}` }, [TOKEN])
  expect(JSON.stringify(asString).includes(TOKEN)).toBe(false)
  expect(asString.tool_use_id).toBe('t1')
  const nested = redactBlock(
    { type: 'tool_result', tool_use_id: 't2', content: [{ type: 'text', text: 'DB_PASSWORD=hunter2pw' }] },
    [],
  )
  expect(JSON.stringify(nested).includes('hunter2pw')).toBe(false)
})

test('a bare value stops at markup that follows it', () => {
  const value = '3dc8abcdef0123456789907b'
  const out = redact(`<bash-stdout>PUBLIC_KEY=${value}</bash-stdout><bash-stderr></bash-stderr>`, [])
  expect(out).toBe(`<bash-stdout>PUBLIC_KEY=${mask(value)}</bash-stdout><bash-stderr></bash-stderr>`)
})

test('an empty value never takes the next line', () => {
  const text = '22\t#STRIPE_WEBHOOK_SECRET=\n23\t#STRIPE_CHECKOUT_SUCCESS_URL=https://elpibe.es/'
  expect(redact(text, [])).toBe(text)
})

test('leaves already-masked text alone', () => {
  const once = redact(`API_KEY=${TOKEN}`, [TOKEN])
  expect(redact(once, [TOKEN])).toBe(once)
})
