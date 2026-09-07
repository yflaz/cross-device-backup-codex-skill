# Setup and recovery

Use this reference only for enablement, scheduling, handoff, restore, or disablement.

## Local configuration

Keep machine-specific configuration outside the skill and outside project repositories. Suggested location:

- macOS/Linux: `~/.config/codex-relay/<slug>.json`
- Windows: `%LOCALAPPDATA%\CodexRelay\<slug>.json`

Example:

```json
{
  "project": "/absolute/path/to/project",
  "slug": "my-project",
  "device": "macbook",
  "session_repo": "/absolute/path/to/private-session-repo",
  "project_remote": "origin",
  "idle_seconds": 90,
  "push": true
}
```

Use a different `device` value on every computer. On Windows, JSON paths must escape backslashes or use forward slashes.

The private session repository stores one bundle per project and device:

```text
projects/<slug>/devices/<device>/codex-all.codexbundle
```

Separate device paths prevent one computer from silently overwriting another computer's last good bundle. Ordinary Git reconciliation happens in the dedicated session repository.

## Scheduler

Run `scripts/backup_project.py --config <absolute-config-path>` every 5–10 minutes.

- macOS: create a user LaunchAgent with `StartInterval`; use absolute paths for Python, the script, and config. Set stdout/stderr log paths under `~/Library/Logs/CodexRelay/`.
- Windows: create a per-user Task Scheduler task running `python.exe` or `py.exe` with the script and config arguments. Set it to run whether or not Codex is open, prevent overlapping instances, and retry after failure.

Do not schedule imports. Import only during an intentional device handoff, because importing changes local Codex session files.

## Source snapshots

The runner creates commits through a temporary index and publishes them to:

```text
refs/heads/codex-backup/<device>
```

This captures tracked and non-ignored untracked files without modifying the real index. Files excluded by `.gitignore` are intentionally not captured. The project must already have at least one normal commit.

Automatic snapshot commits are recovery artifacts, not replacements for clear human-facing commits.

## macOS and Windows handoff

1. Let the source device finish a successful scheduled backup, or run the runner once manually.
2. On the destination device, fetch/pull the project and private session repositories.
3. Restore source changes from the appropriate `codex-backup/<source-device>` branch only if they are not already in the normal project branch.
4. From the destination project root, inspect the session import with `cct import <bundle> --dry-run`.
5. Import using the current working directory mapping supported by the installed `cct` version, commonly `--merge --map-cwd-here`.
6. Reopen or reconcile Codex and verify the expected thread.

Do not assume POSIX and Windows paths match. Never rewrite source-device bundles in place just to change paths.

## Private plaintext repositories

When the user chooses plaintext storage, verify the repository visibility before the first push. Still exclude authentication and secrets. Private visibility reduces accidental exposure but does not protect against account compromise, collaborators, or later visibility changes.

## Failure behavior

- If project files changed within the idle threshold, skip the source snapshot without failing the session backup.
- If `cct` fails, keep the previous bundle.
- If GitHub is unavailable, keep local refs and commits so a later run can retry.
- If authentication fails repeatedly, report it through the scheduler log or OS notification; never prompt from a background job.
- If a source file changes during snapshot construction, accept the consistent Git object snapshot that was read; the next run captures later changes.
- Never repair or rewrite Codex SQLite automatically.
