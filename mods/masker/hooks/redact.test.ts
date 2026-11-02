import { expect, test } from 'claude-code/testing'
import { isHighEntropy, mask, parseEnv, pickSecrets, redact, redactBlock, scan } from './redact'
import { GENERIC, RULES } from './rules.generated'

// Fake secrets, built at run time so this file holds no token-shaped literal.
let seed = 7
const ALNUM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
const rand = (n: number, abc = ALNUM): string =>
  Array.from({ length: n }, () => abc[((seed = (seed * 1103515245 + 12345) % 2 ** 31) >>> 8) % abc.length]).join('')

const TOKEN = 'sk-ant-api03-AbCdEfGh1234567890XyZ'
const PEM_BODY = Array.from({ length: 4 }, () => rand(64)).join('\n')
const DB_PASS = rand(20)

// [rule, secret, text it appears in]
const PROVIDERS: [string, string, string][] = [
  ['github', `ghp_${rand(36)}`, 'GITHUB_TOKEN=%s'],
  ['aws', `AKIA${rand(16, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')}`, 'aws_access_key_id = %s'],
  ['anthropic', `sk-ant-api03-${rand(93)}AA`, 'export ANTHROPIC_API_KEY="%s"'],
  ['stripe', `sk_live_${rand(24)}`, 'stripe.api_key = "%s"'],
  ['slack', `xoxb-${rand(11, '0123456789')}-${rand(12, '0123456789')}-${rand(24)}`, 'SLACK=%s done'],
  ['jwt', `eyJ${rand(30)}.eyJ${rand(40)}.${rand(43)}`, 'Authorization: Bearer %s'],
  ['pem', `-----BEGIN RSA PRIVATE KEY-----\n${PEM_BODY}\n-----END RSA PRIVATE KEY-----`, 'key.pem:\n%s\n'],
  ['credential url', DB_PASS, `DATABASE_URL=postgres://admin:%s@db.internal:5432/app`],
  ['generic', rand(32), 'api_key = "%s"'],
]
const fill = (text: string, secret: string) => text.replace('%s', secret)

test('every rule compiles in the mod runtime', () => {
  for (const r of [...RULES, GENERIC]) expect(() => new RegExp(r.source, `${r.flags}dg`)).not.toThrow()
  expect(RULES.length).toBeGreaterThan(300)
})

test('mask keeps head and tail only', () => {
  expect(mask(TOKEN)).toBe(`sk-a…[REDACTED:${TOKEN.length}]…0XyZ`)
  expect(mask('hunter2pw')).toBe('hu…[REDACTED:9]…pw')
  expect(mask('short')).toBe('[REDACTED:5]')
})

test('masks provider secrets and only the secret part', () => {
  for (const [name, secret, text] of PROVIDERS) {
    const out = redact(fill(text, secret), [])
    if (out.includes(secret)) throw new Error(`${name} not masked: ${out}`)
    expect(out).toContain(`[REDACTED:${secret.length}]`)
  }
  expect(redact(fill(PROVIDERS[0][2], PROVIDERS[0][1]), [])).toContain('GITHUB_TOKEN=ghp_…')
  expect(redact(`postgres://admin:${DB_PASS}@db.internal:5432/app`, [])).toContain('postgres://admin:')
  expect(redact(`postgres://admin:${DB_PASS}@db.internal:5432/app`, [])).toContain('@db.internal:5432/app')
})

test('leaves config that is not a secret alone', () => {
  const texts = [
    '{"auth": {"type": "basic"}, "tokens": ["a", "b"], "auth_cfg":{"x": 1}}',
    'token: true',
    'api_key = os.getenv("API_KEY")',
    'const apiKey = process.env.STRIPE_API_KEY',
    'password: changeme',
    'auth_method: basic_auth',
    'secret_name: prod-db-password-2',
    'access_token_url: https://example.com/oauth/token',
    'PUBLIC_KEY=3dc8abcdef0123456789907b',
    '22\t#STRIPE_WEBHOOK_SECRET=\n23\t#STRIPE_CHECKOUT_SUCCESS_URL=https://elpibe.es/',
    'masker: env snapshot failed; env values not masked, pattern rules still active',
    'masker: input contains a masked secret ([REDACTED…]).',
  ]
  for (const text of texts) expect(redact(text, [])).toBe(text)
})

test('picks env secrets by name or entropy, skips ordinary vars', () => {
  const env = parseEnv(
    ['HOME=/Users/me', 'PATH=/usr/bin:/bin', 'PWD=/tmp/project', `MY_API_KEY=${TOKEN}`,
     'DB_PASSWORD=hunter2pw', 'RANDOM_BLOB=Zx9#qL2!vR8@mT4$wK7%', 'SHELL=/bin/zsh'].join('\0'),
  )
  expect(pickSecrets(env)).toEqual([TOKEN, 'Zx9#qL2!vR8@mT4$wK7%', 'hunter2pw'])
  expect(isHighEntropy('/usr/local/bin/something-long')).toBe(false)
})

test('masks exact env values anywhere, even low-entropy ones', () => {
  const out = redact(`curl -u admin:hunter2pw and ${TOKEN}`, [TOKEN, 'hunter2pw'])
  expect(out.includes(TOKEN) || out.includes('hunter2pw')).toBe(false)
  expect(scan('x hunter2pw', ['hunter2pw'])[0].rule).toBe('env')
})

test('masks tool_result content, string and nested blocks', () => {
  const asString = redactBlock({ type: 'tool_result', tool_use_id: 't1', content: `out ${TOKEN}` }, [TOKEN])
  expect(JSON.stringify(asString).includes(TOKEN)).toBe(false)
  expect(asString.tool_use_id).toBe('t1')
  const nested = redactBlock(
    { type: 'tool_result', tool_use_id: 't2', content: [{ type: 'text', text: 'DB_PASSWORD=hunter2pw' }] },
    ['hunter2pw'],
  )
  expect(JSON.stringify(nested).includes('hunter2pw')).toBe(false)
})

test('redacting twice changes nothing more', () => {
  const text = PROVIDERS.map(([, s, t]) => fill(t, s)).join('\n') + `\nAPI_KEY=${TOKEN}`
  const once = redact(text, [TOKEN])
  expect(redact(once, [TOKEN])).toBe(once)
})

test('scans 1 MB with a pathological curl line in under 1 s', () => {
  const curl = Array.from({ length: 6 }, () => `curl ${'-x a '.repeat(400)}`).join('\n')
  const chunk = `${PROVIDERS.map(([, s, t]) => fill(t, s)).join('\n')}\n${'lorem ipsum token key auth 42 '.repeat(30)}\n`
  const text = curl + chunk.repeat(Math.ceil(1_000_000 / chunk.length))
  const started = Date.now()
  redact(text, [])
  const ms = Date.now() - started
  if (ms > 1000) throw new Error(`took ${ms} ms`)
})
