# masker

Masks secrets before Claude reads them, and refuses writes that would put a masked value back on disk.

## Credits

masker is **heavily inspired by [gitleaks](https://github.com/gitleaks/gitleaks) and its successor [betterleaks](https://github.com/betterleaks/betterleaks)**, both by Zachary Rice and contributors. It does not run either tool. It reuses their work as data and ideas:

- Its provider rules (regexes, keywords, entropy cutoffs) are generated from betterleaks' default config, [`config/betterleaks.toml`](https://github.com/betterleaks/betterleaks/blob/v1.9.0/config/betterleaks.toml) at tag `v1.9.0`.
- Its generic detector is betterleaks' `generic-api-key` rule, with the regex, entropy cutoff, stopword list and context denylist from that rule's filter.
- Its design follows the betterleaks blog series: [Regex is (almost) all you need](https://lookingatcomputer.substack.com/p/regex-is-almost-all-you-need), [Rare not random](https://lookingatcomputer.substack.com/p/rare-not-random), [Express YourCELf](https://lookingatcomputer.substack.com/p/express-yourcelf-filtering-and-validating) and the [other posts](https://lookingatcomputer.substack.com/) on generic secret detection.

Betterleaks is MIT licensed. Its license text is in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).

## What it does

- At session start, reads the environment and collects secret values: variables whose name contains KEY, TOKEN, SECRET, PASSWORD, AUTH, etc., plus high-entropy values. These are masked wherever they appear, at any entropy.
- Runs about 400 betterleaks provider rules (GitHub, AWS, Anthropic, Stripe, Slack, JWTs, private keys, credential URLs, …). A rule runs only when the text contains one of its keywords. Only the secret part is masked: `postgres://admin:Xk9q…[REDACTED:20]…7wQz@db:5432/app`.
- Runs betterleaks' generic rule for `key = value` secrets with no known prefix. A value is masked only when it has high entropy, holds a character other than letters, `_`, `.` and `-`, contains no stopword, and its key isn't on the denylist (`public_key`, `secret_name`, `csrf_token`, …). So `auth: basic`, `token: true` and `api_key = os.getenv("X")` stay readable.
- Masks in tool results, prompts and attachments. Example: `sk-t…[REDACTED:26]…7890`.
- Refuses an @-mentioned file that holds a likely secret, naming the rules that matched. Asking Claude to `Read` the file instead gives a masked copy.
- Refuses `Write`, `Edit`, `MultiEdit`, `NotebookEdit` and `Bash` calls whose input contains a `[REDACTED…]` marker, so a masked value never overwrites the real secret.
- If masking or checking fails, the content is withheld or the mention refused, never passed through unmasked.

## Install

```
/plugin marketplace add <this-repo>
/plugin install masker@ddhq-mkpl
```

No configuration, and nothing to install on the system.

## Limits

This reduces accidental exposure. It is not a security boundary.

- Low-entropy secrets in files (`DB_PASSWORD=hunter2pw`) are masked only when the same value is in the environment. Betterleaks' `generic-password` rule is not imported: its filter is too large to port.
- Betterleaks' `filter` and `validate` programs are not run, apart from the entropy cutoffs and the generic rule's filter above. Low-confidence, path-scoped and component-only rules are not imported. The generated file lists every rule left out.
- No token-efficiency scoring ("Rare not random"): it needs a 1.7 MB tokenizer vocabulary.
- Rules run on the JavaScript regex engine, not RE2. A pathological input could be slow. Hooks are skipped after 10 s; @-mentions are then refused, other content withheld.
- Output that transforms a secret (for example `echo $KEY | base64`) is not caught.
- Env values shorter than 8 characters are not collected. Env vars set after the session starts are masked only when a rule matches them.
- Env-value masking needs the CLI. Elsewhere, only the rules run.
- Where Claude Code's built-in guard loads (machines with managed settings, or a Team or Enterprise `/login`), installed mods don't receive attachments, hook context or compaction summaries. So `SessionStart`/`UserPromptSubmit` hook output and compaction summaries are **not masked** there, and `/plugin` shows no note for it. @-mentioned files are still checked, since mentions reach this mod. Only an organization-deployed mod closes the rest of this gap.
- Built on Claude Code's early-access plugin hooks API, which may change between releases.

## Updating rules

`hooks/rules.generated.ts` is generated. Don't edit it by hand. To move to a new betterleaks tag:

```
curl -sL -H 'Accept: application/vnd.github.raw' \
  'https://api.github.com/repos/betterleaks/betterleaks/contents/config/betterleaks.toml?ref=<tag>' > betterleaks.toml
node scripts/import-betterleaks.ts betterleaks.toml <tag>
claude plugin test .
```

Node 22.6 or later runs the script directly. It fails loudly if the config's layout changed, and prints the rules it kept and dropped. Update the tag in this README's credits.

## Development

```
claude plugin test .
claude plugin validate .
node scripts/check-fixture.ts test/example.env
```

`test/example.env` is a fake `.env` whose sections say what masker should do with each entry: `[mask]`, `[keep]`, `[known-miss]` (false negatives) and `[known-fp]` (false positives). The script prints a verdict per entry and fails on a missed secret or a masked non-secret. Use the same file for a manual run: `cat` it through Bash, and @-mention it.
