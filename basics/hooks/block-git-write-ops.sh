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
# Format: "<subcmd>=<ERE matching one allowed argument>".
# An invocation passes only when *every* argument matches the regex, so a bare
# ref name (`git branch foo`) or a write flag (-d, -D, -m, -M, -c, -u, ...)
# still gets blocked. Add a line here to open up another subcommand.
readonly_args=(
  "branch=-(a|r|l|v|vv|vvv|i|q)|--(all|remotes|list|verbose|quiet|color|no-color|column|no-column|show-current|ignore-case|omit-empty|no-abbrev)|--(contains|no-contains|merged|no-merged|points-at|sort|format|abbrev)(=[^[:space:]]+|[[:space:]]+[^-[:space:]][^[:space:]]*)"
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
    arg_re=${entry#*=}
    if printf '%s' "$segment" | grep -Eqi "^[[:space:]]*git([[:space:]]+-[^[:space:]]+([[:space:]]+[^-[:space:]][^[:space:]]*)?)*[[:space:]]+${subcmd}([[:space:]]+(${arg_re}))*[[:space:]]*$"; then
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