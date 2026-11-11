#!/bin/sh
# statusline-command.sh — 3-line dashboard for Claude Code
# Layout (no box borders):
#   Line 1: MODEL  <model> [effort]          SESSION  id:<id>  │  turns:<n>  │  ~$<cost>          BRANCH  <branch>
#   Line 2: [bar] <pct>% (<cur>k/<N>k tokens)          CACHE  write ↑<n>%  │  read ↓<n>%
#   Line 3: [bar] <pct>% used (resets at <HH:MM>)
#   Line 4: EMU  <n> windowed  │  <n> headless (only while an emulator runs; only counts > 0)

input=$(cat)

# ── helpers ──────────────────────────────────────────────────────────────────

# pad_right: pad plain string $1 to display-character-length $2 with spaces
# Uses wc -m (character count) to handle multi-byte UTF-8 chars like │ ↑ ↓
pad_right() {
  _pr_str="$1"
  _pr_w="$2"
  _pr_len=$(printf '%s' "$_pr_str" | wc -m | tr -d ' ')
  printf '%s' "$_pr_str"
  _pr_pad=$(( _pr_w - _pr_len ))
  _pr_i=0
  while [ "$_pr_i" -lt "$_pr_pad" ]; do
    printf ' '
    _pr_i=$(( _pr_i + 1 ))
  done
}

# print_bar_colored: print a 10-block bar for percentage $2 with filled blocks in color $1
# $1 = ANSI color escape (e.g. '\033[0;32m'), $2 = integer percentage 0-100
print_bar_colored() {
  color="$1"
  pct="$2"
  filled_count=$(awk "BEGIN{printf \"%d\", int($pct / 10)}")
  empty_count=$((10 - filled_count))
  if [ "$filled_count" -gt 0 ]; then
    printf "${color}"
    i=0
    while [ "$i" -lt "$filled_count" ]; do
      printf '█'
      i=$((i + 1))
    done
    printf '\033[0m'
  fi
  if [ "$empty_count" -gt 0 ]; then
    printf '\033[90m'
    i=0
    while [ "$i" -lt "$empty_count" ]; do
      printf '░'
      i=$((i + 1))
    done
    printf '\033[0m'
  fi
}

# ── parse fields ──────────────────────────────────────────────────────────────

cwd=$(echo "$input" | jq -r '.cwd // .workspace.current_dir // ""')
wt_branch=$(echo "$input" | jq -r '.worktree.branch // empty')
if [ -n "$wt_branch" ]; then
  branch="$wt_branch"
else
  branch=$(git --no-optional-locks -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

model_id=$(echo "$input" | jq -r '.model.id // empty')
effort=$(echo "$input" | jq -r '.effort.level // empty')

session_id=$(echo "$input" | jq -r '.session_id // empty')
turn_count=$(echo "$input" | jq -r '.turn_count // empty')
cost_usd=$(echo "$input" | jq -r '.cost_usd // empty')

used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
max_tokens=$(echo "$input" | jq -r '.context_window.max_tokens // .context_window.context_window_size // empty')
cur_tokens=$(echo "$input" | jq -r '.context_window.total_input_tokens // empty')

cache_write_pct=$(echo "$input" | jq -r '.cache_write_percentage // empty')
cache_read_pct=$(echo "$input" | jq -r '.cache_read_percentage // empty')

rate_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
rate_resets=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')

# ── LINE 1: MODEL + SESSION ───────────────────────────────────────────────────

# --- MODEL content ---
if [ -n "$model_id" ]; then
  if [ -n "$effort" ]; then
    model_plain="${model_id} [${effort}]"
  else
    model_plain="${model_id}"
  fi
else
  model_plain=""
fi

# --- SESSION content ---
session_plain=""
if [ -n "$session_id" ]; then
  short_id=$(printf '%s' "$session_id" | cut -c1-8)
  session_plain="id:${short_id}"
fi
if [ -n "$turn_count" ]; then
  if [ -n "$session_plain" ]; then
    session_plain="${session_plain}  │  turns:${turn_count}"
  else
    session_plain="turns:${turn_count}"
  fi
fi
if [ -n "$cost_usd" ]; then
  cost_fmt=$(printf '~$%.3f' "$cost_usd")
  if [ -n "$session_plain" ]; then
    session_plain="${session_plain}  │  ${cost_fmt}"
  else
    session_plain="${cost_fmt}"
  fi
fi

# Line 1: BRANCH  <content>          SESSION  <content>          MODEL  <content>
# "BRANCH  " = 8 chars; pad branch content to 31 so total first column = 39 chars
# then 2 spaces gap, then "SESSION  " = 9 chars, then session content
branch_padded=$(pad_right "$branch" 31)
printf '\033[1;97mBRANCH\033[0m  \033[0;32m%s\033[0m' "$branch_padded"
printf '  '
printf '\033[1;97mSESSION\033[0m  \033[0;97m%s\033[0m' "$session_plain"
if [ -n "$model_plain" ]; then
  printf '  '
  printf '\033[1;97mMODEL\033[0m  \033[0;36m%s\033[0m' "$model_plain"
fi
printf '\n'

# ── LINE 2: CONTEXT bar + optional CACHE ─────────────────────────────────────

# Determine context bar data
if [ -n "$used_pct" ]; then
  used_int=$(printf '%.0f' "$used_pct")
  if [ -n "$max_tokens" ]; then
    max_k=$(awk "BEGIN{printf \"%d\", int($max_tokens / 1000 + 0.5)}")
  else
    max_k="?"
  fi
  if [ -n "$cur_tokens" ]; then
    cur_k=$(awk "BEGIN{printf \"%d\", int($cur_tokens / 1000 + 0.5)}")
  else
    cur_k="?"
  fi
  if [ "$used_int" -ge 80 ]; then
    bar_color='\033[0;31m'
  elif [ "$used_int" -ge 50 ]; then
    bar_color='\033[0;33m'
  else
    bar_color='\033[0;32m'
  fi
fi

# Determine if cache section has data
cw_int=0
cr_int=0
cache_has_data=0
if [ -n "$cache_write_pct" ] || [ -n "$cache_read_pct" ]; then
  [ -n "$cache_write_pct" ] && cw_int=$(printf '%.0f' "$cache_write_pct")
  [ -n "$cache_read_pct" ]  && cr_int=$(printf '%.0f' "$cache_read_pct")
  if [ "$cw_int" -gt 0 ] || [ "$cr_int" -gt 0 ]; then
    cache_has_data=1
  fi
fi

# CACHE content string
cache_plain=""
if [ "$cw_int" -gt 0 ]; then
  cache_plain="write ↑${cw_int}%"
fi
if [ "$cr_int" -gt 0 ]; then
  if [ -n "$cache_plain" ]; then
    cache_plain="${cache_plain}  │  read ↓${cr_int}%"
  else
    cache_plain="read ↓${cr_int}%"
  fi
fi

# Line 2: [bar] <pct>% (<cur>k/<N>k tokens)          CACHE  <content>
# The bar "[" + 10 blocks + "]" = 12 display chars
# First column target width = 39 chars: bar(12) + text + padding = 39
# then 2 spaces, then "CACHE  " (7) + cache content
if [ -n "$used_pct" ]; then
  printf '\033[90m[\033[0m'
  print_bar_colored "$bar_color" "$used_int"
  printf '\033[90m]\033[0m'
  after_bar=" ${used_int}% (${cur_k}k/${max_k}k tokens)"
  after_bar_len=$(printf '%s' "$after_bar" | wc -m | tr -d ' ')
  # first col = 39: bar=12, text=after_bar_len, pad fills remainder
  pad_len=$((39 - 12 - after_bar_len))
  [ "$pad_len" -lt 0 ] && pad_len=0
  printf '\033[0;97m%s\033[0m' "$after_bar"
  i=0
  while [ "$i" -lt "$pad_len" ]; do
    printf ' '
    i=$((i + 1))
  done
else
  # no context data: blank first column
  printf '%-39s' ""
fi

if [ "$cache_has_data" -eq 1 ]; then
  printf '  '
  printf '\033[1;97mCACHE\033[0m  \033[0;33m%s\033[0m' "$cache_plain"
fi
printf '\n'

# ── LINE 3: 5H RATE ───────────────────────────────────────────────────────────

if [ -n "$rate_pct" ] && [ -n "$rate_resets" ]; then
  rate_int=$(printf '%.0f' "$rate_pct")
  reset_time=$(date -r "$rate_resets" +%H:%M 2>/dev/null)

  # bar color
  if [ "$rate_int" -ge 80 ]; then
    rate_bar_color='\033[0;31m'
  elif [ "$rate_int" -ge 50 ]; then
    rate_bar_color='\033[0;33m'
  else
    rate_bar_color='\033[0;32m'
  fi

  # Line 3: [bar] <pct>% used  │  resets at <HH:MM>
  printf '\033[90m[\033[0m'
  print_bar_colored "$rate_bar_color" "$rate_int"
  printf '\033[90m]\033[0m'

  printf '\033[0;97m %d%% used (resets at %s)\033[0m\n' \
    "$rate_int" "$reset_time"
fi

# ── LINE 4: EMU (only while an emulator runs) ─────────────────────────────────

# Count running Android emulators (qemu-system); headless ones carry -no-window
emu_procs=$(pgrep -fl qemu-system 2>/dev/null)
emu_headless=$(printf '%s\n' "$emu_procs" | grep -c -- -no-window)
emu_windowed=$(printf '%s\n' "$emu_procs" | grep qemu-system | grep -vc -- -no-window)
emu_plain=""
[ "$emu_windowed" -gt 0 ] && emu_plain="${emu_windowed} windowed"
if [ "$emu_headless" -gt 0 ]; then
  [ -n "$emu_plain" ] && emu_plain="${emu_plain}  │  "
  emu_plain="${emu_plain}${emu_headless} headless"
fi
if [ -n "$emu_plain" ]; then
  printf '\033[1;97mEMU\033[0m  \033[0;35m%s\033[0m\n' "$emu_plain"
fi
