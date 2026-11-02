// Generates hooks/rules.generated.ts from betterleaks' default config.
//
//   curl -sL -H 'Accept: application/vnd.github.raw' \
//     'https://api.github.com/repos/betterleaks/betterleaks/contents/config/betterleaks.toml?ref=v1.9.0' > betterleaks.toml
//   node scripts/import-betterleaks.ts betterleaks.toml v1.9.0
//
// Dev-time only (Node 22.6+ runs .ts directly). The mod never runs this.
import { readFileSync, writeFileSync } from 'node:fs'

const [file, tag] = process.argv.slice(2)
if (!file || !tag) throw new Error('usage: node scripts/import-betterleaks.ts <betterleaks.toml> <tag>')

type Rule = { id: string; source: string; flags: string; keywords: string[]; groups: number[]; minEntropy?: number }

const KEEP_CONFIDENCE = new Set(['high', 'medium'])
// Emitted as GENERIC with the data its filter needs; hooks/redact.ts applies it.
const GENERIC_ID = 'generic-api-key'

const field = (block: string, key: string): string | undefined =>
  block.match(new RegExp(`^${key} = (?:'''(.*?)'''|"(.*?)"|(\\d+))$`, 'm'))?.slice(1).find(v => v !== undefined)

const keywordsOf = (block: string): string[] => {
  const list = block.match(/^keywords = \[([^\]]*)\]/m)?.[1]
  if (list === undefined) return []
  return [...list.matchAll(/"([^"]+)"/g)].map(m => m[1].toLowerCase())
}

// Lowest entropy the rule's filter accepts, when its filter states one.
const minEntropyOf = (block: string): number | undefined => {
  const n = block.match(/(?:filter\.)?entropy\(finding\["secret"\]\) <=? ([\d.]+)/)?.[1]
  return n === undefined ? undefined : Number(n)
}

/** Index just past the group that encloses `from`, or the source's end. */
const enclosingEnd = (src: string, from: number): number => {
  let depth = 0
  for (let i = from; i < src.length; i++) {
    const c = src[i]
    if (c === '\\') i++
    else if (c === '[') {
      for (i++; i < src.length && src[i] !== ']'; i++) if (src[i] === '\\') i++
    } else if (c === '(') depth++
    else if (c === ')' && depth-- === 0) return i
  }
  return src.length
}

/** RE2 syntax to JS: leading flags, mid-pattern (?i), (?P<name>, POSIX classes, \z. */
const toJs = (re2: string): { source: string; flags: string } => {
  let source = re2
  let flags = ''
  const lead = source.match(/^\(\?([ims]+)\)/)
  if (lead) {
    flags = lead[1]
    source = source.slice(lead[0].length)
  }
  source = source
    .replaceAll('(?P<', '(?<')
    .replaceAll('[:alnum:]', 'a-zA-Z0-9')
    .replaceAll('[:alpha:]', 'a-zA-Z')
    .replaceAll('[:digit:]', '0-9')
    .replaceAll('\\z', '$')
  for (let at = source.indexOf('(?i)'); at !== -1; at = source.indexOf('(?i)')) {
    const end = enclosingEnd(source, at + 4)
    source = `${source.slice(0, at)}(?i:${source.slice(at + 4, end)})${source.slice(end)}`
  }
  return { source, flags }
}

/** Unnamed capture groups hold the secret, named ones context; failing those, a `password` group. */
const secretGroups = (src: string): number[] => {
  const out: number[] = []
  let n = 0
  let password: number | undefined
  for (let i = 0; i < src.length; i++) {
    const c = src[i]
    if (c === '\\') i++
    else if (c === '[') {
      for (i++; i < src.length && src[i] !== ']'; i++) if (src[i] === '\\') i++
    } else if (c === '(') {
      if (src[i + 1] !== '?') out.push(++n)
      else if (src[i + 2] === '<' && src[i + 3] !== '=' && src[i + 3] !== '!') {
        n++
        if (src.startsWith('password>', i + 3)) password = n
      }
    }
  }
  return out.length || password === undefined ? out : [password]
}

const text = readFileSync(file, 'utf8')
const blocks = text.split(/^\[\[rules\]\]$/m).slice(1)
if (blocks.length < 100) throw new Error(`expected [[rules]] blocks, found ${blocks.length}: layout changed?`)

const rules: Rule[] = []
const dropped: string[] = []
for (const block of blocks) {
  const id = field(block, 'id')
  if (!id) throw new Error(`rule without id:\n${block.slice(0, 200)}`)
  const regex = field(block, 'regex')
  const confidence = field(block, 'confidence')
  const why =
    id === GENERIC_ID ? null
    : !regex ? 'no regex'
    : !KEEP_CONFIDENCE.has(confidence ?? '') ? `confidence ${confidence}`
    : field(block, 'path') ? 'path-scoped'
    : /^skipReport = true$/m.test(block) ? 'component only'
    : undefined
  if (why === null) continue
  if (why) {
    dropped.push(`${id} (${why})`)
    continue
  }
  const { source, flags } = toJs(regex!)
  try {
    new RegExp(source, `${flags}dg`)
  } catch (err) {
    dropped.push(`${id} (${(err as Error).message})`)
    continue
  }
  const secretGroup = field(block, 'secretGroup')
  rules.push({
    id,
    source,
    flags,
    keywords: keywordsOf(block),
    groups: secretGroup ? [Number(secretGroup)] : secretGroups(source),
    minEntropy: minEntropyOf(block),
  })
}

/** The generic rule, plus its filter's stopwords and context denylist. */
const genericOf = (block: string) => {
  const need = <T>(v: T | undefined, what: string): T => {
    if (v === undefined) throw new Error(`${GENERIC_ID}: ${what} not found: filter layout changed?`)
    return v
  }
  const stopList = need(
    block.match(/containsAny\(finding\["secret"\], \[([^\]]*)\]\) \|\| filter\.matchesAny\(genericMatchContext/)?.[1],
    'stopwords',
  )
  const context = need(
    block.match(/\]\) \|\| filter\.matchesAny\(genericMatchContext, \[`(.+?)`\]\)\)$/m)?.[1],
    'context denylist',
  )
  return {
    id: GENERIC_ID,
    ...toJs(need(field(block, 'regex'), 'regex')),
    keywords: keywordsOf(block),
    groups: [1],
    minEntropy: need(minEntropyOf(block), 'entropy cutoff'),
    stopwords: [...stopList.matchAll(/"([^"]+)"/g)].map(m => m[1]),
    context: toJs(context),
  }
}
const genericBlock = blocks.find(b => field(b, 'id') === GENERIC_ID)
if (!genericBlock) throw new Error(`${GENERIC_ID} not found`)
const generic = genericOf(genericBlock)
new RegExp(generic.source, `${generic.flags}dg`)
new RegExp(generic.context.source, generic.context.flags)

const out = `// GENERATED by scripts/import-betterleaks.ts from betterleaks ${tag} config/betterleaks.toml.
// Do not edit by hand. Betterleaks is MIT licensed: see THIRD_PARTY_NOTICES.
// Kept ${rules.length} of ${blocks.length} rules. Dropped:
${dropped.map(d => `//   ${d}`).join('\n')}

export type Rule = {
  id: string
  source: string
  flags: string
  /** Lowercased; the rule runs only when the text contains one. Empty: always runs. */
  keywords: readonly string[]
  /** Capture groups holding the secret, first non-empty wins; none: the whole match. */
  groups: readonly number[]
  /** A secret at or under this Shannon entropy is ignored. */
  minEntropy?: number
}

export const RULES: readonly Rule[] = ${JSON.stringify(rules, null, 2)}

/** ${GENERIC_ID}: a keyword, an assignment, a value. Its filter drops values holding a stopword
 * and matches whose \`[\\w.-]*\` prefix plus match fits \`context\`. */
export const GENERIC: Rule & { stopwords: readonly string[]; context: { source: string; flags: string } } =
  ${JSON.stringify(generic)}
`
writeFileSync(new URL('../hooks/rules.generated.ts', import.meta.url), out)
console.log(`kept ${rules.length} + ${GENERIC_ID} (${generic.stopwords.length} stopwords), dropped ${dropped.length}:\n${dropped.join('\n')}`)
