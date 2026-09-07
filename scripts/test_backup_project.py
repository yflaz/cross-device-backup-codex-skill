#!/usr/bin/env python3
"""Focused self-test for the temporary-index source snapshot invariant."""

from pathlib import Path
import subprocess
import tempfile
import unittest

import backup_project


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True,
                          check=True).stdout.strip()


class SnapshotTest(unittest.TestCase):
    def test_snapshot_does_not_change_worktree_or_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cdb-test-") as temp_dir:
            root = Path(temp_dir)
            git(root, "init", "-q")
            git(root, "config", "user.name", "Backup Test")
            git(root, "config", "user.email", "backup-test@example.invalid")
            (root / "tracked.txt").write_text("base\n", encoding="utf-8")
            git(root, "add", "tracked.txt")
            git(root, "commit", "-q", "-m", "base")
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
            (root / "staged.txt").write_text("staged\n", encoding="utf-8")
            git(root, "add", "staged.txt")
            (root / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            before = git(root, "status", "--porcelain=v1")

            changed, push_ok = backup_project.snapshot_project({
                "project": str(root), "device": "test-device", "idle_seconds": 0, "push": False
            })

            self.assertTrue(changed)
            self.assertTrue(push_ok)
            self.assertEqual(before, git(root, "status", "--porcelain=v1"))
            tree_listing = git(root, "ls-tree", "-r", "--name-only", "refs/codex-backup/test-device")
            self.assertIn("tracked.txt", tree_listing)
            self.assertIn("staged.txt", tree_listing)
            self.assertIn("untracked.txt", tree_listing)


if __name__ == "__main__":
    unittest.main()
