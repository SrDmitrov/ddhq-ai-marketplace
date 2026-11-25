#!/usr/bin/env python3
"""Detect project copies of the basics plugin hooks.

Older setups copied the hooks into the project's .claude/hooks/ and registered
them in .claude/settings.json. Those copies run next to the plugin's own hooks,
and the stricter one wins, so an outdated copy keeps blocking what the plugin
now allows.

Usage:
  check_stale_hooks.py           SessionStart hook: reads the hook JSON on stdin
                                 and prints a warning as hook JSON, or nothing.
  check_stale_hooks.py --list [DIR]
                                 Prints one finding per line for DIR (default:
                                 the current directory), or nothing.
Always exits 0.
"""

import json
import os
import sys

HOOK_NAMES = ("block-git-write-ops.sh", "block-dangerous-file-ops.sh")
SETTINGS_FILES = ("settings.json", "settings.local.json")


def find_stale(project_dir):
    claude_dir = os.path.join(project_dir, ".claude")
    findings = []
    for name in HOOK_NAMES:
        path = os.path.join(claude_dir, "hooks", name)
        if os.path.isfile(path):
            findings.append("file: .claude/hooks/%s" % name)
    for settings in SETTINGS_FILES:
        try:
            with open(os.path.join(claude_dir, settings)) as f:
                hooks = json.load(f).get("hooks") or {}
        except (OSError, ValueError, AttributeError):
            continue
        for event, groups in hooks.items():
            for group in groups if isinstance(groups, list) else []:
                for hook in (group.get("hooks") or []) if isinstance(group, dict) else []:
                    command = hook.get("command", "") if isinstance(hook, dict) else ""
                    if any(name in command for name in HOOK_NAMES):
                        findings.append("settings: .claude/%s hooks.%s: %s" % (settings, event, command))
    return findings


def main(argv):
    if argv[1:2] == ["--list"]:
        for line in find_stale(argv[2] if len(argv) > 2 else os.getcwd()):
            print(line)
        return 0

    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    findings = find_stale(project_dir)
    if not findings:
        return 0
    text = (
        "Stale copies of the basics plugin hooks found in this project. They run next to the "
        "plugin's own hooks and may block commands the plugin allows:\n- "
        + "\n- ".join(findings)
        + "\nRun /basics:install-rules to remove them, or delete the files and their settings entries."
    )
    print(json.dumps({
        "systemMessage": text,
        "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
