"""Regression table for block_git_write_ops.py.

Run from this directory: python3 -m unittest test_block_git_write_ops -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from block_git_write_ops import check

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "block_git_write_ops.py")

# Read-only or non-git commands that must pass with git writes not allowed.
MUST_PASS = [
    "git status",
    "git fetch --all --prune -q 2>&1 | tail -3",
    "git branch -a",
    "git branch -a --list '*EPSE-193*'",
    "git branch --list 'bugfix/*'",
    "git branch -a 2>/dev/null",
    "git -C sub branch --show-current",
    "git reflog -5",
    "git reflog show HEAD",
    "git tag --list",
    "git tag -l 'v1.*'",
    "git clean -n",
    "git clean -nd",
    "git log -Sfix --oneline",
    "echo 'see git branch docs'",
    'grep -rn "git push" docs/',
    "grep -f patterns.txt file",
    "[ -f deploy/local.yml ] && echo ok",
    "test -f a && cp -f a b",
    "docker compose -f deploy/local.yml ps",
    "tail -f logs/app.log",
    "make -f Makefile.dev",
    "git log --oneline | grep 'git reset'",
    "cat <<'EOF'\ngit push --force\ngit reset --hard\nEOF",
    "cat <<EOF > notes.md\nrun git merge later\nEOF\necho done",
    "command -v git",
    "echo '$HOME' && git diff",
]

# Commands that must be blocked with git writes not allowed: (command, rule).
MUST_BLOCK = [
    ("git push", "dangerous-subcmd 'push'"),
    ("git commit -m 'x'", "dangerous-subcmd 'commit'"),
    ('git commit -m "fix; git reset docs"', "dangerous-subcmd 'commit'"),
    ("git status && git checkout main", "dangerous-subcmd 'checkout'"),
    ("git status\ngit push", "dangerous-subcmd 'push'"),
    ("sudo git push", "dangerous-subcmd 'push'"),
    ("sudo -u bob git push", "dangerous-subcmd 'push'"),
    ("env GIT_DIR=x git push", "dangerous-subcmd 'push'"),
    ("FOO=1 /usr/bin/git merge dev", "dangerous-subcmd 'merge'"),
    ("echo $(git push)", "dangerous-subcmd 'push'"),
    ('echo "$(git push)"', "dangerous-subcmd 'push'"),
    ("echo `git merge dev`", "dangerous-subcmd 'merge'"),
    ("(cd a; git push)", "dangerous-subcmd 'push'"),
    ("git -C repo --no-pager rebase main", "dangerous-subcmd 'rebase'"),
    ("git branch foo", "dangerous-subcmd 'branch'"),
    ("git branch --list foo -m bar", "dangerous-subcmd 'branch'"),
    ("git reflog expire --all", "dangerous-subcmd 'reflog'"),
    ("git tag v1", "dangerous-subcmd 'tag'"),
    ("git clean -fd", "dangerous-subcmd 'clean'"),
    ("git clean -f", "force"),
    ("git clean -d", "dangerous-subcmd 'clean'"),
    ("git reset --hard", "dangerous-subcmd 'reset'"),
    ("git branch -D x", "branch-delete"),
    ("cat <<EOF\nok\nEOF\ngit pull", "dangerous-subcmd 'pull'"),
    ("echo '<<EOF'\ngit push", "dangerous-subcmd 'push'"),
    ("git commit -m 'unbalanced", "dangerous-subcmd 'commit'"),
]

# Blocked even when DDHQ_ALLOW_GIT=1.
ALWAYS_BLOCKED = [
    ("git push -f", "force"),
    ("git push --force", "force"),
    ("git push --force-with-lease origin x", "force"),
    ("git push -fu origin x", "force"),
    ("git push origin +main", "force"),
    ("git checkout -f main", "force"),
    ("git branch -D x", "branch-delete"),
    ("git branch --delete x", "branch-delete"),
    ("git branch -dr origin/x", "branch-delete"),
    ("git merge dev", "dangerous-subcmd 'merge'"),
]


class TestDefault(unittest.TestCase):
    def test_must_pass(self):
        for cmd in MUST_PASS:
            with self.subTest(cmd=cmd):
                self.assertIsNone(check(cmd))

    def test_must_block(self):
        for cmd, rule in MUST_BLOCK:
            with self.subTest(cmd=cmd):
                hit = check(cmd)
                self.assertIsNotNone(hit)
                self.assertEqual(hit[0], rule)


class TestAllowModes(unittest.TestCase):
    def test_allow_1(self):
        for cmd in ("git push", "git commit -m x", "git checkout -b x", "git branch x"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(check(cmd, allow="1"))
        for cmd, rule in ALWAYS_BLOCKED:
            with self.subTest(cmd=cmd):
                self.assertEqual(check(cmd, allow="1")[0], rule)

    def test_allow_local(self):
        for cmd in ("git commit -m x", "git checkout main", "git branch x"):
            with self.subTest(cmd=cmd):
                self.assertIsNone(check(cmd, allow="local"))
        self.assertEqual(check("git push", allow="local")[0], "dangerous-subcmd 'push'")


class TestMessage(unittest.TestCase):
    def run_hook(self, command, cwd="/"):
        env = dict(os.environ)
        env.pop("DDHQ_ALLOW_GIT", None)
        data = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd})
        return subprocess.run([sys.executable, HOOK], input=data, capture_output=True, text=True, env=env)

    def test_block_names_rule_and_segment_only(self):
        r = self.run_hook("git fetch -q && git status && git push origin main")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Blocked (rule: dangerous-subcmd 'push'): git push origin main", r.stderr)
        self.assertNotIn("fetch", r.stderr)

    def test_pass_and_other_tools(self):
        self.assertEqual(self.run_hook("git status").returncode, 0)
        data = json.dumps({"tool_name": "Read", "tool_input": {}})
        r = subprocess.run([sys.executable, HOOK], input=data, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class TestLinkedWorktree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.main = os.path.join(cls.tmp, "main")
        cls.linked = os.path.join(cls.tmp, "linked")
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(git + ["init", "-q", cls.main], check=True)
        subprocess.run(git + ["-C", cls.main, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        subprocess.run(git + ["-C", cls.main, "worktree", "add", "-q", "-b", "wt", cls.linked], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_checkout_allowed_in_linked_worktree(self):
        self.assertIsNone(check("git checkout -b feature", cwd=self.linked))

    def test_checkout_blocked_in_main_worktree(self):
        self.assertEqual(check("git checkout -b feature", cwd=self.main)[0], "dangerous-subcmd 'checkout'")

    def test_exception_off_with_cd_or_global_opts(self):
        self.assertIsNotNone(check("cd .. && git checkout main", cwd=self.linked))
        self.assertIsNotNone(check("git -C ../main checkout main", cwd=self.linked))


if __name__ == "__main__":
    unittest.main()
