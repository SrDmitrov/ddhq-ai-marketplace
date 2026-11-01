#!/usr/bin/env bash
# PreToolUse hook: hard-block obviously destructive file operations.
# Exit 2 => tool call is denied and the message on stderr is shown to Claude.

set -uo pipefail

input=$(cat)

tool=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')
[ "$tool" = "Bash" ] || exit 0

command=$(printf '%s' "$input" | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')

# Block any rm with -r and -f (in any order)
if printf '%s' "$command" | grep -Eqi 'rm[[:space:]]+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)'; then
  echo "Blocked: rm with -r and -f. Command: $command" >&2
  exit 2
fi

# Block bare `rm -rf` or `rm -fr` even if arguments are weirdly spaced
if printf '%s' "$command" | grep -Eqi 'rm[[:space:]]+-rf([[:space:]]|$)|rm[[:space:]]+-fr([[:space:]]|$)'; then
  echo "Blocked: rm -rf / -fr. Command: $command" >&2
  exit 2
fi

# Block mv or cp that target root-level or very broad paths
if printf '%s' "$command" | grep -Eqi '(mv|cp)[[:space:]]+.*[[:space:]]+(/|/\*|/\{)'; then
  echo "Blocked: mv/cp targeting root or broad paths. Command: $command" >&2
  exit 2
fi

exit 0