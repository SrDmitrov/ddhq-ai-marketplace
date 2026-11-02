// Pure masking logic: no `$`, so tests import it directly.
import { GENERIC, RULES, type Rule } from './rules.generated.ts'

const SECRET_WORDS =
  /KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|CREDENTIAL|AUTH|PRIVATE|SESSION|COOKIE|DSN|CONN/i
const NOT_SECRET_NAME = /^(PWD|OLDPWD|SSH_AUTH_SOCK)$|^XPC_|KEYCHAIN/i

export const MASK_MARKER = /\[REDACTED(:\d+)?\]/
const MIN_SECRET_LENGTH = 8

export const isSecretName = (name: string): boolean =>
  SECRET_WORDS.test(name) && !NOT_SECRET_NAME.test(name)

const entropy = (s: string): number => {
  const counts = new Map<string, number>()
  for (const c of s) counts.set(c, (counts.get(c) ?? 0) + 1)
  let bits = 0
  for (const n of counts.values()) bits -= (n / s.length) * Math.log2(n / s.length)
  return bits
}

export const isHighEntropy = (v: string): boolean => {
  if (v.length < 20 || /\s/.test(v)) return false
  if (/^[\/~]/.test(v) || v.includes(':')) return false // paths, URLs, PATH-like lists
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z\d]/].filter(r => r.test(v)).length
  return classes >= 3 && entropy(v) >= 3.5
}

/** Secret values in `env`, longest first so a value inside another masks whole. */
export const pickSecrets = (env: Record<string, string>): string[] =>
  [
    ...new Set(
      Object.entries(env)
        .filter(([k, v]) => v.length >= MIN_SECRET_LENGTH && (isSecretName(k) || isHighEntropy(v)))
        .map(([, v]) => v),
    ),
  ].sort((a, b) => b.length - a.length)

export const mask = (v: string): string => {
  const keep = v.length >= 16 ? 4 : v.length >= MIN_SECRET_LENGTH ? 2 : 0
  if (keep === 0) return `[REDACTED:${v.length}]`
  return `${v.slice(0, keep)}…[REDACTED:${v.length}]…${v.slice(-keep)}`
}

/** Parses `env -0` output. */
export const parseEnv = (stdout: string): Record<string, string> => {
  const env: Record<string, string> = {}
  for (const entry of stdout.split('\0')) {
    const eq = entry.indexOf('=')
    if (eq > 0) env[entry.slice(0, eq)] = entry.slice(eq + 1)
  }
  return env
}

export type Span = { start: number; end: number; rule: string }

type Compiled = Rule & { re: RegExp }
const compile = (rule: Rule): Compiled => ({ ...rule, re: new RegExp(rule.source, `${rule.flags}dg`) })
const PROVIDERS = RULES.map(compile)
const GENERIC_RULE = compile(GENERIC)
const GENERIC_CONTEXT = new RegExp(GENERIC.context.source, GENERIC.context.flags)
const GENERIC_PREFIX = /[\w.-]{0,50}$/
// betterleaks: a generic secret needs one character outside these.
const ONLY_WORDY = /^[a-zA-Z_.-]+$/
// A value this mod already masked: never mask it again.
const MASKED = /\S{0,4}…\[REDACTED:\d+\]…\S{0,4}|\[REDACTED(?::\d+)?\]/g

const isGenericSecret = (text: string, start: number, match: string, secret: string): boolean => {
  if (ONLY_WORDY.test(secret) || GENERIC.stopwords.some(w => secret.includes(w))) return false
  const prefix = text.slice(Math.max(0, start - 50), start).match(GENERIC_PREFIX)?.[0] ?? ''
  return !GENERIC_CONTEXT.test(prefix + match)
}

function* ruleSpans(text: string, lower: string, rule: Compiled): Generator<Span> {
  if (rule.keywords.length > 0 && !rule.keywords.some(k => lower.includes(k))) return
  for (const m of text.matchAll(rule.re)) {
    const group = rule.groups.find(i => m[i])
    const [start, end] = group === undefined ? [m.index, m.index + m[0].length] : m.indices![group]!
    const secret = text.slice(start, end)
    if (secret.length === 0) continue
    if (rule.minEntropy !== undefined && entropy(secret) <= rule.minEntropy) continue
    if (rule === GENERIC_RULE && !isGenericSecret(text, m.index, m[0], secret)) continue
    yield { start, end, rule: rule.id }
  }
}

/** Likely secrets in `text`: exact env values, betterleaks provider rules, then its generic rule. */
export const scan = (text: string, secrets: readonly string[] = []): Span[] => {
  const spans: Span[] = []
  for (const s of secrets) {
    for (let at = text.indexOf(s); at !== -1; at = text.indexOf(s, at + s.length)) {
      spans.push({ start: at, end: at + s.length, rule: 'env' })
    }
  }
  const lower = text.toLowerCase()
  for (const rule of [...PROVIDERS, GENERIC_RULE]) spans.push(...ruleSpans(text, lower, rule))
  const masked = [...text.matchAll(MASKED)].map(m => [m.index, m.index + m[0].length])
  return spans.filter(s => !masked.some(([a, b]) => s.start < b && a < s.end))
}

/** Spans sorted and overlaps joined, so each secret masks whole once. */
const merge = (spans: Span[]): Span[] => {
  const out: Span[] = []
  for (const s of [...spans].sort((a, b) => a.start - b.start || b.end - a.end)) {
    const last = out.at(-1)
    if (last && s.start < last.end) last.end = Math.max(last.end, s.end)
    else out.push({ ...s })
  }
  return out
}

export const redact = (text: string, secrets: readonly string[]): string => {
  let out = ''
  let at = 0
  for (const { start, end } of merge(scan(text, secrets))) {
    out += text.slice(at, start) + mask(text.slice(start, end))
    at = end
  }
  return at === 0 ? text : out + text.slice(at)
}

export type Block = { type: string; [field: string]: unknown }

/** Masks a Messages API block's readable text: text blocks and tool_result content. */
export const redactBlock = (block: Block, secrets: readonly string[]): Block => {
  if (block.type === 'text' && typeof block.text === 'string') {
    return { ...block, text: redact(block.text, secrets) }
  }
  if (block.type === 'tool_result') {
    const { content } = block
    if (typeof content === 'string') return { ...block, content: redact(content, secrets) }
    if (Array.isArray(content)) return { ...block, content: (content as Block[]).map(b => redactBlock(b, secrets)) }
  }
  return block
}
