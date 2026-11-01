// Pure masking logic: no `$`, so tests import it directly.

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

// NAME=value, NAME: value, "NAME": "value", export NAME='value'.
const PAIR =
  /(["']?)([A-Za-z_][A-Za-z0-9_.-]*)\1([ \t]*[:=][ \t]*)(?:"([^"\n]*)"|'([^'\n]*)'|([^\s"',}#<]+))/g

const maskPairs = (text: string): string =>
  text.replace(PAIR, (whole, q: string, name: string, sep: string, dq?: string, sq?: string, bare?: string) => {
    const value = dq ?? sq ?? bare ?? ''
    if (!isSecretName(name) || value.length === 0 || MASK_MARKER.test(value)) return whole
    const quoted = dq !== undefined ? `"${mask(value)}"` : sq !== undefined ? `'${mask(value)}'` : mask(value)
    return `${q}${name}${q}${sep}${quoted}`
  })

export const redact = (text: string, secrets: readonly string[]): string => {
  let out = text
  for (const s of secrets) if (out.includes(s)) out = out.split(s).join(mask(s))
  return maskPairs(out)
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
