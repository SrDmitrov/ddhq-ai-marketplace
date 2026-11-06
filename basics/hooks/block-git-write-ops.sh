#!/usr/bin/env bash
# PreToolUse hook: block dangerous git operations in Bash commands.
# Exit 2 => tool call is denied and the message on stderr is shown to Claude.

set -uo pipefail

input=$(cat)

tool=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')
[ "$tool" = "Bash" ] || exit 0

command=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')
cwd=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("cwd",""))')

# Block any command containing --force or standalone -f
if printf '%s' "$command" | grep -Eq -- '--force|[[:space:]]-f([[:space:]]|$)'; then
  echo "Blocked: --force / -f detected. Command: $command" >&2
  exit 2
fi

# Block branch deletion (-d, -D, --delete, or combined flags like -dr) even when
# DDHQ_ALLOW_GIT=1 opts the project into other branch writes.
if printf '%s' "$command" | grep -Eq -- '(^|[;&|[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?branch([[:space:]][^;&|]*)?[[:space:]](-[[:alpha:]]*[dD][[:alpha:]]*|--delete)([[:space:]]|$)'; then
  echo "Blocked: git branch deletion requires explicit user instruction. Command: $command" >&2
  exit 2
fi

# Dangerous git subcommands that require explicit user approval
dangerous_subcmds=(
  merge
  rebase
  reset
  pull
  tag
  clean
  gc
  prune
  reflog
  filter-branch
  filter-repo
  replace
)

# Day-to-day git writes. A project opts in by setting DDHQ_ALLOW_GIT=1 in the
# "env" block of its .claude/settings.json (done by the install-rules skill).
#
# Exception: `git checkout` is allowed inside a linked worktree (not the main
# one), detected via the hook's cwd: a linked worktree's git dir
# (.git/worktrees/<name>) differs from the common git dir. The exception is
# off when the command changes directory (cd/pushd), since cwd would no
# longer describe where git runs.
in_linked_worktree=0
if [ "${DDHQ_ALLOW_GIT:-0}" != "1" ]; then
  dangerous_subcmds+=(commit push checkout branch)
  if [ -n "$cwd" ] && ! printf '%s' "$command" | grep -Eq '(^|[^[:alnum:]_-])(cd|pushd)([^[:alnum:]_-]|$)'; then
    git_dir=$(git -C "$cwd" rev-parse --path-format=absolute --git-dir 2>/dev/null)
    common_dir=$(git -C "$cwd" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
    [ -n "$git_dir" ] && [ "$git_dir" != "$common_dir" ] && in_linked_worktree=1
  fi
fi

# Build a regex alternation: (commit|push|merge|...)
subcmds_re=$(IFS='|'; echo "${dangerous_subcmds[*]}")

# Read-only escape hatch for the subcommands above.
# Format: "<subcmd>=<ERE matching the whole argument tail>" (each argument is
# preceded by whitespace). An invocation passes only when its full tail
# matches, so anything unrecognised -- a bare ref name (`git branch foo`,
# `git tag v1`), a write flag (-d, -D, -m, -f, ...) or a write subcommand
# (`reflog expire`) -- still gets blocked. Matching is case-sensitive.
# Add a line here to open up another subcommand.
S='[[:space:]]+'
POS='[^-[:space:]][^[:space:]]*'          # positional: ref, pattern or path
VAL="(=[^[:space:]]+|${S}${POS})"         # value of an option that takes one
filter_opts="--(contains|no-contains|merged|no-merged|points-at|sort|format)${VAL}"
branch_opts="-(a|r|v|vv|vvv|i|q)|--(all|remotes|verbose|quiet|show-current|ignore-case|omit-empty|no-abbrev|no-color|no-column)|--(color|column)(=[^[:space:]]+)?|--abbrev${VAL}|${filter_opts}"
tag_opts="-n[0-9]*|-i|--(ignore-case|omit-empty|no-color|no-column)|--(color|column)(=[^[:space:]]+)?|${filter_opts}"
clean_opts="-[dxXq]+|--quiet|-e${S}${POS}|--exclude=[^[:space:]]+"
clean_dry="-n|--dry-run|-[dxXq]*n[dxXqn]*"
readonly_args=(
  # Listing options; positionals (patterns) only after -l/--list.
  "branch=(${S}(${branch_opts}))*(${S}(-l|--list)(${S}(${branch_opts}|${POS}))*)?"
  "tag=(${S}(${tag_opts}))*(${S}(-l|--list)(${S}(${tag_opts}|${POS}))*)?"
  # Bare/options only, `show ...`, or `exists <ref>`; never expire/delete.
  "reflog=(${S}-[^[:space:]]+)*|${S}show(${S}[^[:space:]]+)*|${S}exists${S}${POS}"
  # Dry run only: -n/--dry-run required, no -f/-i in combined flags.
  "clean=(${S}(${clean_opts}))*${S}(${clean_dry})(${S}(${clean_opts}|${clean_dry}))*(${S}--)?(${S}${POS})*"
)

# Split on shell separators so each git invocation is checked on its own,
# then drop the ones that are fully read-only.
segments=$(printf '%s' "$command" | tr '|;&\n' '\n\n\n\n')
scrubbed=""
while IFS= read -r segment; do
  allowed=0
  # Plain `git checkout ...` (no global options like -C/--git-dir) in a linked worktree.
  if [ "$in_linked_worktree" -eq 1 ] && printf '%s' "$segment" | grep -Eqi '^[[:space:]]*git[[:space:]]+checkout([[:space:]]|$)'; then
    allowed=1
  fi
  [ "$allowed" -eq 1 ] || for entry in "${readonly_args[@]}"; do
    subcmd=${entry%%=*}
    tail_re=${entry#*=}
    if printf '%s' "$segment" | grep -Eq "^[[:space:]]*git([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*[[:space:]]+${subcmd}(${tail_re})[[:space:]]*$"; then
      allowed=1
      break
    fi
  done
  [ "$allowed" -eq 1 ] || scrubbed="${scrubbed}
${segment}"
done <<EOF
$segments
EOF

# Match git invocations anywhere in the command line.
# This is intentionally simple: if you need more precision, refine here.
if printf '%s' "$scrubbed" | grep -Eqi "(^|[;&|]|[[:space:]])git[[:space:]]+(-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?[[:space:]]+)*(${subcmds_re})([[:space:]]|$)"; then
  echo "Blocked: this git command requires explicit user instruction. Command: $command" >&2
  exit 2
fi

exit 0