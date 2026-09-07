#!/usr/bin/env python3
"""Non-invasive, opt-in backup of one Git project and its Codex sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "target", "__pycache__"}


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
        check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"{' '.join(cmd)}: {detail}")
    return result


def newest_project_mtime(root: Path) -> float:
    newest = 0.0
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in files:
            try:
                newest = max(newest, (Path(current) / name).stat().st_mtime)
            except (FileNotFoundError, PermissionError):
                continue
    return newest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_sessions(cfg: dict, cct: str) -> bool:
    session_repo = Path(cfg["session_repo"]).expanduser().resolve()
    destination = session_repo / "projects" / cfg["slug"] / "devices" / cfg["device"] / "codex-all.codexbundle"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cdb-session-") as temp_dir:
        candidate = Path(temp_dir) / "codex-all.codexbundle"
        run([cct, "export", "--project", str(Path(cfg["project"]).resolve()), "-o", str(candidate)])
        if not candidate.is_file() or candidate.stat().st_size == 0:
            raise RuntimeError("cct produced no session bundle")
        if destination.exists() and sha256(candidate) == sha256(destination):
            return False
        os.replace(candidate, destination)
    return True


def commit_session_repo(cfg: dict) -> tuple[bool, bool]:
    repo = Path(cfg["session_repo"]).expanduser().resolve()
    relative = Path("projects") / cfg["slug"] / "devices" / cfg["device"] / "codex-all.codexbundle"
    run(["git", "add", "--", str(relative)], cwd=repo)
    staged = run(["git", "diff", "--cached", "--quiet", "--", str(relative)], cwd=repo, check=False)
    if staged.returncode == 0:
        return False, True
    if staged.returncode != 1:
        raise RuntimeError("could not inspect session repository staging area")
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run(["git", "commit", "-m", f"backup({cfg['slug']}): {cfg['device']} {stamp}"], cwd=repo)
    if cfg.get("push", True):
        pushed = run(["git", "push"], cwd=repo, check=False)
        if pushed.returncode:
            print(f"session push queued for retry: {pushed.stderr.strip()}", file=sys.stderr)
            return True, False
    return True, True


def snapshot_project(cfg: dict) -> tuple[bool, bool]:
    project = Path(cfg["project"]).expanduser().resolve()
    idle_seconds = int(cfg.get("idle_seconds", 90))
    if time.time() - newest_project_mtime(project) < idle_seconds:
        print(f"source snapshot skipped: project changed within {idle_seconds}s")
        return False, True

    head = run(["git", "rev-parse", "--verify", "HEAD"], cwd=project).stdout.strip()
    device = cfg["device"].replace("/", "-")
    local_ref = f"refs/codex-backup/{device}"
    remote_ref = f"refs/heads/codex-backup/{device}"
    previous_result = run(["git", "rev-parse", "--verify", local_ref], cwd=project, check=False)
    parent = previous_result.stdout.strip() if previous_result.returncode == 0 else head

    with tempfile.TemporaryDirectory(prefix="cdb-index-") as temp_dir:
        index = str(Path(temp_dir) / "index")
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = index
        env["GIT_OPTIONAL_LOCKS"] = "0"
        run(["git", "read-tree", "HEAD"], cwd=project, env=env)
        run(["git", "add", "-A", "--", "."], cwd=project, env=env)
        tree = run(["git", "write-tree"], cwd=project, env=env).stdout.strip()

    parent_tree = run(["git", "rev-parse", f"{parent}^{{tree}}"], cwd=project).stdout.strip()
    if tree == parent_tree:
        return False, True
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    commit = run(["git", "commit-tree", tree, "-p", parent, "-m",
                  f"Automated recovery snapshot from {cfg['device']} at {stamp}"], cwd=project).stdout.strip()
    old = parent if previous_result.returncode == 0 else ""
    update = ["git", "update-ref", local_ref, commit]
    if old:
        update.append(old)
    run(update, cwd=project)
    if cfg.get("push", True):
        remote = cfg.get("project_remote", "origin")
        pushed = run(["git", "push", remote, f"{commit}:{remote_ref}"], cwd=project, check=False)
        if pushed.returncode:
            print(f"source snapshot push queued for retry: {pushed.stderr.strip()}", file=sys.stderr)
            return True, False
    return True, True


def validate(cfg: dict) -> None:
    required = {"project", "slug", "device", "session_repo"}
    missing = sorted(required - cfg.keys())
    if missing:
        raise RuntimeError(f"missing config fields: {', '.join(missing)}")
    project = Path(cfg["project"]).expanduser().resolve()
    session_repo = Path(cfg["session_repo"]).expanduser().resolve()
    if not (project / ".git").exists():
        raise RuntimeError(f"project is not a Git repository: {project}")
    if not (session_repo / ".git").exists():
        raise RuntimeError(f"session_repo is not a Git repository: {session_repo}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    config_path = args.config.expanduser().resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    validate(cfg)
    cct = shutil.which(cfg.get("cct", "cct"))
    if not cct:
        raise RuntimeError("cct was not found on PATH; install codex-claude-transfer first")
    if args.dry_run:
        print(json.dumps({"status": "ready", "project": cfg["project"], "slug": cfg["slug"],
                          "device": cfg["device"], "session_repo": cfg["session_repo"]}, indent=2))
        return 0
    lock_path = config_path.with_suffix(config_path.suffix + ".lock")
    if lock_path.exists() and time.time() - lock_path.stat().st_mtime > 3600:
        lock_path.unlink(missing_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        print("another backup is already running; skipped")
        return 0
    try:
        os.write(lock_fd, str(os.getpid()).encode("ascii"))
        session_changed = export_sessions(cfg, cct)
        session_committed, session_push_ok = commit_session_repo(cfg) if session_changed else (False, True)
        source_changed, source_push_ok = snapshot_project(cfg)
        print(json.dumps({"session_updated": session_changed, "session_committed": session_committed,
                          "session_push_ok": session_push_ok, "source_snapshot": source_changed,
                          "source_push_ok": source_push_ok}))
        return 0 if session_push_ok and source_push_ok else 2
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"cross-device-backup: {exc}", file=sys.stderr)
        raise SystemExit(1)
