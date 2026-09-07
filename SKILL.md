---
name: cross-device-backup
description: Configure and operate opt-in, cross-device backups for one explicitly named Codex project, including resumable local sessions, durable context files, and non-invasive Git snapshots. Use only when the user explicitly invokes this skill or clearly says that the current project needs cross-device backup; never apply it to unrelated projects or chats.
---

# Cross-device Backup

Protect only the project the user explicitly opts in. Do not scan, register, export, stop, restart, or modify other Codex projects or tasks.

## Invariants

- Never stop Codex or interrupt another task to make a backup.
- Never copy or publish `auth.json`, credentials, environment files, keychains, cookies, caches, locks, or the whole Codex home.
- Keep source code in its existing project repository and Codex session bundles in a separate private repository.
- Plaintext session bundles are allowed only when the user explicitly chooses them and confirms the destination repository is private. Otherwise recommend encryption without silently enabling it.
- Use a temporary Git index for automatic source snapshots. Never change the user's branch, working tree, staging area, stash, or normal commit history.
- Background jobs must not invoke a model. They must continue working when Codex usage is exhausted.
- Treat backup as best-effort durability, not a bit-perfect copy of live processes or external connector state.

## Enable a project

Before mutation, resolve the exact project root, its Git remote, the separate session-backup repository, and a stable project slug. If GitHub authentication or either remote is missing, prepare everything that is local, then ask only for the missing login or repository information.

Read [references/setup.md](references/setup.md) when enabling, disabling, restoring, or moving a project between operating systems.

Create these durable context files only if absent, adapting them to the project rather than overwriting existing documentation:

- `AGENTS.md`: stable project instructions, validation commands, and boundaries.
- `docs/PROJECT_STATE.md`: current verified state and active milestone.
- `docs/DECISIONS.md`: consequential decisions and rationale.
- `docs/NEXT.md`: concrete continuation point, blockers, and unfinished work.

Do not update those files on a timer. Update them at meaningful milestones, before a device handoff, and when an interrupted task would otherwise be hard to resume.

Install or locate `cct` from [ahmojo/codex-claude-transfer](https://github.com/ahmojo/codex-claude-transfer). Prefer a published binary or documented package manager. Verify the installed command with `cct doctor` before relying on it.

Create a project-specific configuration outside the public skill repository. Register only the selected project. Configure the OS scheduler to call `scripts/backup_project.py` every 5–10 minutes with a 90-second project idle threshold. Use macOS `launchd` or Windows Task Scheduler; do not use a Codex scheduled task because model availability is the failure being mitigated.

Run one foreground dry run and one real backup. Confirm:

1. The real Git index and working tree are unchanged.
2. A source snapshot exists under `codex-backup/<device>` on the project's existing remote.
3. A project-scoped `.codexbundle` exists in the private session repository.
4. The session repository push succeeds, or a local commit remains queued for retry.
5. No authentication or excluded sensitive files were included.

## Normal operation

Let the native scheduler run independently. If the project is actively changing, the runner skips the source snapshot and retries later. Session export uses a temporary output and replaces the last good bundle only after a successful export. A failure must preserve the previous good backup and return a nonzero status for logging or notification.

Do not announce routine successful background backups inside the working conversation. Surface only setup results, repeated failures, a requested status check, or a device handoff.

## Device handoff and restore

Before continuing on another device, fetch the source repository and the session repository. Select the newest bundle for this project and import it with a dry run first. Use `--merge` and the documented working-directory mapping when macOS and Windows project paths differ. Restart or reconcile Codex only when the user is ready to switch; never do so while unrelated tasks are running.

After import, verify that the intended thread is discoverable and that the repository commit/worktree matches the session's expected state. If native session import fails, use the durable context files to start a fresh task rather than repeatedly rewriting Codex indexes.

## Disable

Remove only the scheduler entry and configuration for the named project. Preserve remote backups unless the user explicitly asks to delete them. Never disable other registered projects.
