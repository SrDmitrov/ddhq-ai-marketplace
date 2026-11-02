// Checks a sectioned fixture (see test/example.env) against masker's detector.
//
//   node scripts/check-fixture.ts test/example.env
//
// Scans the whole file as the mod would, then judges each entry by the section it sits in.
// Exits 1 when a [mask] entry is missed or a [keep] entry is masked.
import { readFileSync } from 'node:fs'
import { scan } from '../hooks/redact.ts'

const file = process.argv[2]
if (!file) throw new Error('usage: node scripts/check-fixture.ts <fixture>')

const text = readFileSync(file, 'utf8')
const spans = scan(text)

type Section = 'mask' | 'keep' | 'known-miss' | 'known-fp'
const VERDICT: Record<Section, [masked: string, kept: string]> = {
  mask: ['ok', 'FALSE NEGATIVE'],
  keep: ['FALSE POSITIVE', 'ok'],
  'known-miss': ['now masked: move to [mask]', 'ok (known miss)'],
  'known-fp': ['ok (known false positive)', 'now kept: move to [keep]'],
}

let section: Section | undefined
let offset = 0
let failed = 0
for (const [i, line] of text.split('\n').entries()) {
  const start = offset
  offset += line.length + 1
  const header = line.match(/^# \[(mask|keep|known-miss|known-fp)\]$/)
  if (header) section = header[1] as Section
  // Entries only: skip comments, blank lines and the lines of a multi-line value.
  if (!section || !/^(?:export )?[A-Za-z_][A-Za-z0-9_]*=/.test(line)) continue
  const masked = spans.filter(s => s.start < offset - 1 && start < s.end)
  const verdict = VERDICT[section][masked.length > 0 ? 0 : 1]
  if (verdict === 'FALSE NEGATIVE' || verdict === 'FALSE POSITIVE') failed++
  const rules = [...new Set(masked.map(s => s.rule))].join(', ')
  console.log(`${String(i + 1).padStart(3)} ${verdict.padEnd(28)} ${rules.padEnd(28)} ${line.split('=')[0]}`)
}
console.log(failed ? `\n${failed} unexpected result(s)` : '\nall entries as expected')
process.exit(failed ? 1 : 0)
