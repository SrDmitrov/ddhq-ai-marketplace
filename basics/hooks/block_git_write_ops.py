#!/usr/bin/env python3
"""PreToolUse hook: block dangerous git operations in Bash commands.

Exit 2 => the tool call is denied and the message on stderr is shown to Claude.

The command is tokenized with shlex, so text inside quotes or heredoc bodies is
never read as a git invocation, and only real git segments are checked:

  force             git ... -f / --force / --force-with-lease / push +ref
  branch-delete     git branch -d / -D / --delete (always blocked)
  dangerous-subcmd  merge, rebase, reset, ... plus commit/push/checkout/branch
                    depending on DDHQ_ALLOW_GIT

Day-to-day git writes. A project opts in via DDHQ_ALLOW_GIT in the "env" block
of its .claude/settings.json (set by the install-rules skill):
  unset/other  commit, push, checkout and branch are blocked
  local        commit, checkout and branch allowed; push blocked
  1            commit, push, checkout and branch allowed

Exception: `git checkout` is allowed inside a linked worktree (not the main
one), detected via the hook's cwd: a linked worktree's git dir
(.git/worktrees/<name>) differs from the common git dir. The exception is off
when the command changes directory (cd/pushd), since cwd would no longer
describe where git runs, and when git global options (-C, --git-dir, ...) are
used.

Tests: python3 -m unittest test_block_git_write_ops (from this directory).
"""

import json
import os
import re
import shlex
import subprocess
import sys

# Dangerous git subcommands that always require explicit user approval.
BASE_DANGEROUS = {
    "merge", "rebase", "reset", "pull", "tag", "clean", "gc", "prune",
    "reflog", "filter-branch", "filter-repo", "replace",
}
DAY_TO_DAY = {"commit", "push", "checkout", "branch"}

# Read-only escape hatch for the dangerous subcommands. Each regex must match
# the whole argument tail, where every argument is preceded by one space. An
# invocation passes only when its full tail matches, so anything unrecognised
# -- a bare ref name (`git branch foo`, `git tag v1`), a write flag
# (-d, -D, -m, -f, ...) or a write subcommand (`reflog expire`) -- is still
# blocked. Add an entry here to open up another subcommand.
_S = r"\s+"
_POS = r"[^-\s]\S*"  # positional: ref, pattern or path
_VAL = rf"(=\S+|{_S}{_POS})"  # value of an option that takes one
_FILTER = rf"--(contains|no-contains|merged|no-merged|points-at|sort|format){_VAL}"
_BRANCH = (
    r"-(a|r|v|vv|vvv|i|q)"
    r"|--(all|remotes|verbose|quiet|show-current|ignore-case|omit-empty|no-abbrev|no-color|no-column)"
    rf"|--(color|column)(=\S+)?|--abbrev{_VAL}|{_FILTER}"
)
_TAG = (
    r"-n[0-9]*|-i|--(ignore-case|omit-empty|no-color|no-column)"
    rf"|--(color|column)(=\S+)?|{_FILTER}"
)
_CLEAN = rf"-[dxXq]+|--quiet|-e{_S}{_POS}|--exclude=\S+"
_CLEAN_DRY = r"-n|--dry-run|-[dxXq]*n[dxXqn]*"
READONLY_TAILS = {
    # Listing options; positionals (patterns) only after -l/--list.
    "branch": rf"({_S}({_BRANCH}))*({_S}(-l|--list)({_S}({_BRANCH}|{_POS}))*)?",
    "tag": rf"({_S}({_TAG}))*({_S}(-l|--list)({_S}({_TAG}|{_POS}))*)?",
    # Bare/options only, `show ...`, or `exists <ref>`; never expire/delete.
    "reflog": rf"({_S}-\S+)*|{_S}show({_S}\S+)*|{_S}exists{_S}{_POS}",
    # Dry run only: -n/--dry-run required, no -f/-i in combined flags.
    "clean": (
        rf"({_S}({_CLEAN}))*{_S}({_CLEAN_DRY})"
        rf"({_S}({_CLEAN}|{_CLEAN_DRY}))*({_S}--)?({_S}{_POS})*"
    ),
}

# Commands that run another command given as their arguments.
WRAPPERS = {"sudo", "env", "command", "exec", "nohup", "time", "nice", "xargs", "builtin", "timeout"}
# git global options that take a separate value.
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}

PUNCT = "();<>|&\n"
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_HEREDOC = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1")
_SHORT_FORCE = re.compile(r"-[A-Za-z]*f[A-Za-z]*")
_SHORT_DELETE = re.compile(r"-[A-Za-z]*[dD][A-Za-z]*")
_CHDIR = re.compile(r"(^|[^\w-])(cd|pushd)([^\w-]|$)")


def dangerous_subcmds(allow):
    if allow == "1":
        return BASE_DANGEROUS
    if allow == "local":
        return BASE_DANGEROUS | {"push"}
    return BASE_DANGEROUS | DAY_TO_DAY


def strip_heredocs(cmd):
    """Drop heredoc bodies; keep everything when a terminator is missing."""
    lines = cmd.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in _HEREDOC.finditer(line):
            delim = m.group(2)
            j = i
            while j < len(lines) and lines[j].strip() != delim:
                j += 1
            if j < len(lines):
                i = j + 1
    return "\n".join(out)


def substitutions(cmd):
    """Bodies of $(...) and `...`, found anywhere (also inside double quotes)."""
    bodies = re.findall(r"`([^`]*)`", cmd)
    start = cmd.find("$(")
    while start != -1:
        depth, j = 1, start + 2
        while j < len(cmd) and depth:
            depth += {"(": 1, ")": -1}.get(cmd[j], 0)
            j += 1
        bodies.append(cmd[start + 2:j - 1] if depth == 0 else cmd[start + 2:])
        start = cmd.find("$(", start + 2)
    return bodies


def tokenize(cmd):
    cmd = cmd.replace("\\\n", " ")
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=PUNCT)
        lex.whitespace = " \t\r"  # newline separates commands: keep it as a token
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:
        # Unbalanced quotes: fail closed with a quote-blind split.
        return re.findall(r"[^\s();<>|&]+|[();<>|&\n]+", cmd)


def _is_punct(tok):
    return bool(tok) and all(c in PUNCT for c in tok)


def _is_separator(tok):
    if not _is_punct(tok):
        return False
    if tok[0] in "<>":  # redirection, unless it opens a process substitution
        return any(c in "();|\n" for c in tok)
    return True


def segments(tokens):
    """Split tokens into simple commands, dropping redirections and targets."""
    seg = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
        if _is_separator(tok):
            if seg:
                yield seg
            seg = []
        elif _is_punct(tok):  # redirection operator: skip it and its target
            i += 1
        elif tok.isdigit() and _is_punct(nxt) and nxt[0] in "<>" and not _is_separator(nxt):
            pass  # fd number of a redirection (2>&1)
        else:
            seg.append(tok)
        i += 1
    if seg:
        yield seg


def git_invocation(seg):
    """Return (global_opts, subcmd, args) if the segment runs git, else None."""
    i = 0
    while i < len(seg) and _ASSIGNMENT.match(seg[i]):
        i += 1
    if i >= len(seg):
        return None
    if os.path.basename(seg[i]) in WRAPPERS:
        rest = [k for k in range(i + 1, len(seg)) if os.path.basename(seg[k]) == "git"]
        if not rest:
            return None
        i = rest[0]
    elif os.path.basename(seg[i]) != "git":
        return None
    i += 1
    global_opts = []
    while i < len(seg) and seg[i].startswith("-"):
        global_opts.append(seg[i])
        if seg[i] in GIT_OPTS_WITH_VALUE:
            i += 1
        i += 1
    if i >= len(seg):
        return global_opts, None, []
    return global_opts, seg[i].lower(), seg[i + 1:]


def _flags(args):
    """Arguments before `--` (after it come paths)."""
    return args[:args.index("--")] if "--" in args else args


def in_linked_worktree(cwd):
    def git_dir(flag):
        r = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--path-format=absolute", flag],
            capture_output=True, text=True,
        )
        return r.stdout.strip() if r.returncode == 0 else ""

    gd = git_dir("--git-dir")
    return bool(gd) and gd != git_dir("--git-common-dir")


def check(command, cwd="", allow="0"):
    """Return (rule, segment) for the first blocked git invocation, else None."""
    for body in substitutions(command):
        hit = check(body, cwd, allow)
        if hit:
            return hit

    dangerous = dangerous_subcmds(allow)
    for seg in segments(tokenize(strip_heredocs(command))):
        inv = git_invocation(seg)
        if not inv or not inv[1]:
            continue
        global_opts, subcmd, args = inv
        text = " ".join(seg)
        flags = _flags(args)

        # Flag clusters (-fu) and +refspecs only count for push: elsewhere a
        # cluster with an f is often something else (git log -Sfix).
        if any(a in ("-f", "--force") or a.startswith(("--force-with-lease", "--force-if-includes"))
               or (subcmd == "push" and (_SHORT_FORCE.fullmatch(a) or a.startswith("+")))
               for a in flags):
            return "force", text
        if subcmd == "branch" and any(a == "--delete" or _SHORT_DELETE.fullmatch(a) for a in flags):
            return "branch-delete", text
        if subcmd not in dangerous:
            continue
        tail_re = READONLY_TAILS.get(subcmd)
        if tail_re is not None and re.fullmatch(tail_re, "".join(" " + a for a in args)):
            continue
        if (subcmd == "checkout" and not global_opts and cwd
                and not _CHDIR.search(command) and in_linked_worktree(cwd)):
            continue
        return "dangerous-subcmd '%s'" % subcmd, text
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    hit = check(command, data.get("cwd", ""), os.environ.get("DDHQ_ALLOW_GIT", "0"))
    if not hit:
        return 0
    rule, segment = hit
    print(
        "Blocked (rule: %s): %s\nThis git command requires explicit user instruction." % (rule, segment),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
