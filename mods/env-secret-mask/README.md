# env-secret-mask

Masks secrets before Claude reads them, and refuses writes that would put a masked value back on disk.

## What it does

- At session start, reads the environment and collects secret values: variables whose name contains KEY, TOKEN, SECRET, PASSWORD, AUTH, etc., plus high-entropy values.
- Masks those values, and any `SECRET_NAME=value` pair (.env, YAML, JSON), in tool results, prompts and attachments. Example: `sk-t…[REDACTED:26]…7890`.
- Refuses `Write`, `Edit`, `MultiEdit`, `NotebookEdit` and `Bash` calls whose input contains a `[REDACTED…]` marker, so a masked value never overwrites the real secret.
- If masking fails, the content is withheld rather than passed through unmasked.

## Install

```
/plugin marketplace add <this-repo>
/plugin install env-secret-mask@ddhq-mkpl
```

No configuration.

## Limits

This reduces accidental exposure. It is not a security boundary.

- Output that transforms a secret (for example `echo $KEY | base64`) is not caught.
- Values shorter than 8 characters are not masked.
- Env vars set after the session starts are masked only in `NAME=value` form.
- Env-value masking needs the CLI. Elsewhere, only `NAME=value` masking runs.
- On Team or Enterprise setups, content the organization protects (managed prompt content, organization hooks) bypasses installed plugins, so it is not masked.
- Built on Claude Code's early-access plugin hooks API, which may change between releases.

## Development

```
claude plugin test .
claude plugin validate .
```
