import type { Register } from 'claude-code'
import { MASK_MARKER, parseEnv, pickSecrets, redact, redactBlock } from './redact'

const GUARDED_TOOLS: ReadonlySet<string> = new Set(['Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'])
const WITHHELD = '[env-secret-mask: content withheld, masking failed]'

export const register: Register = on => {
  // Held in the module only: never written to $.state or $.store.
  let secrets: string[] = []

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    try {
      const { exitCode, stdout } = await $.process.run(['/usr/bin/env', '-0'])
      if (exitCode !== 0) throw new Error(`env exited ${exitCode}`)
      secrets = pickSecrets(parseEnv(stdout))
    } catch {
      $.ui.status(`${$.plugin.name}: env snapshot failed; only NAME=value masking active`)
    }
    return started
  })

  // Every row the model reads passes here: tool results, prompts, hook context, subagents.
  on('session.append', ($, e, next) => {
    const content = e.message.content.map(b => redactBlock(b, secrets))
    const changed = JSON.stringify(content) !== JSON.stringify(e.message.content)
    return next(changed ? { ...e, message: { ...e.message, content } } : e)
  }).catch(($, e, next) => {
    if (next.called) return next(e)
    // Fail closed: withhold the row's readable text rather than store it unmasked.
    const content = e.message.content.map(b =>
      b.type === 'text' ? { ...b, text: WITHHELD } : b.type === 'tool_result' ? { ...b, content: WITHHELD } : b,
    )
    return next({ ...e, message: { ...e.message, content } })
  })

  // Attachments rendered per request (@-mentioned files, reminders) bypass session.append.
  on('prompt.attachment', async ($, e, next) => {
    const rendered = await next(e)
    return rendered.text === null ? rendered : { ...rendered, text: redact(rendered.text, secrets) }
  })

  // A masked value written back would overwrite the real secret on disk.
  on('tool.call', ($, e, next) =>
    GUARDED_TOOLS.has(e.tool) && MASK_MARKER.test(JSON.stringify(e))
      ? {
          deny:
            `${$.plugin.name}: input contains a masked secret ([REDACTED…]). ` +
            'Edit around it with a narrower old_string, or reference the env var instead of copying its value.',
        }
      : next(e),
  ).catch(($, e, next) =>
    next.called ? next(e) : { deny: `${$.plugin.name}: its guard failed.` },
  )
}
