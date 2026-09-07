# Codex Relay

> 中文开发者请阅读 [README-CN.md](README-CN.md)。

Codex Relay is an explicit opt-in Codex skill for carrying one selected project between computers without interrupting active work. It protects source changes, project-scoped Codex sessions, and durable working context with native operating-system scheduling that continues after model usage is exhausted.

## The problem

Using the same account on two computers does not guarantee that local Codex projects and conversations are available on both devices. Git solves only part of the problem:

1. project files must be recoverable on another computer;
2. Codex conversations and session metadata must move with the project;
3. decisions and the exact continuation point must survive an incomplete session export;
4. the final backup cannot depend on another model turn, because usage may already be exhausted.

Codex Relay treats these as separate durability layers instead of pretending that one sync mechanism can preserve every kind of state.

## Three-layer continuity model

| Layer | What it protects | Where it is stored |
| --- | --- | --- |
| Source snapshots | Tracked and non-ignored project files, including unfinished changes | `codex-backup/<device>` in the existing project remote |
| Session bundles | Project-scoped Codex conversations, rollout data, metadata, and Git context | A separate private session repository |
| Durable context | Stable instructions, verified state, decisions, blockers, and next steps | `AGENTS.md` and focused files under `docs/` |

```text
Explicit project opt-in
          |
          v
  Native OS scheduler  ---- no model call / no Codex quota
          |
          +---- temporary Git index ----> codex-backup/<device>
          |
          +---- cct project export -----> private session repository
          |
          `---- milestone context ------> AGENTS.md + docs/
```

## Why Codex Relay is different

### Project-scoped and explicit-only

The skill ships with `allow_implicit_invocation: false`. It never scans or registers every Codex project. A project is configured only after the user explicitly invokes `$codex-relay` or clearly requests cross-device continuity for that project.

### Independent of model availability

Scheduled backups run through macOS `launchd` or Windows Task Scheduler. The runner does not invoke a model or create a Codex scheduled task, so it can retry after the conversation can no longer continue because model usage is exhausted.

### Non-invasive Git snapshots

Source snapshots use a temporary Git index. The runner does not switch branches, alter the real staging area, create or apply a stash, clean the worktree, stop Codex, or add automated commits to the project's normal branch history.

### More than conversation export

A session bundle is useful, but it is not a complete image of a running computer. Codex Relay also keeps small durable context documents so a fresh task can recover the verified state and intended next action when native session import is unavailable or incomplete.

### Cross-platform handoff

Each device gets its own name, recovery branch, and session-bundle path. macOS and Windows project paths may differ; path reconciliation happens during an intentional import instead of rewriting saved bundles in place.

## Comparison with related approaches

Codex Relay does not reimplement a session format. It uses [`codex-claude-transfer`](https://github.com/ahmojo/codex-claude-transfer) (`cct`) as its project-level export and import engine, then adds source recovery, durable context, explicit project registration, and quota-independent scheduling.

| Project or approach | Primary focus | What Codex Relay adds or changes |
| --- | --- | --- |
| [`codex-claude-transfer`](https://github.com/ahmojo/codex-claude-transfer) | Session export/import, path mapping, and agent conversion | Source recovery branches, durable context, explicit project enrollment, and native scheduling |
| [`codex-session-sync`](https://github.com/shonngithub/codex-session-sync) | WebDAV synchronization of broader local Codex state | Project-only scope, no WebDAV requirement, and no default collection of the complete local state |
| [`codex-handoff`](https://github.com/Raf4ik/codex-handoff) | Encrypted GUI handoff between devices | An inspectable Skill-and-script workflow that fits existing Git repositories and does not require a dedicated GUI |
| Git alone | Source version control | Recoverable Codex sessions and explicit continuity documents |
| Agent-triggered end-of-task backup | A simple final model action | Native scheduling that still runs when no final model action is available |

The defining combination is: **explicit-only, project-scoped, source + session + durable context, quota-independent, and non-invasive**.

## Repository layout

```text
codex-relay/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── setup.md
└── scripts/
    ├── backup_project.py
    └── test_backup_project.py
```

The recommended runtime layout uses two remote repositories:

```text
project-repository
├── normal branches
└── codex-backup/<device>          automated recovery snapshots

private-session-repository
└── projects/<slug>/devices/<device>/codex-all.codexbundle
```

## Requirements

- Codex CLI or Codex Desktop with local sessions;
- Git;
- Python 3.10 or later;
- [`cct`](https://github.com/ahmojo/codex-claude-transfer), verified with `cct doctor`;
- an existing Git repository for the selected project with at least one normal commit;
- a separate private Git repository for session bundles;
- non-interactive Git authentication for scheduled pushes.

## Installation

macOS or Linux:

```bash
git clone https://github.com/yflaz/cross-device-backup-codex-skill.git \
  ~/.codex/skills/codex-relay
```

Windows PowerShell:

```powershell
git clone https://github.com/yflaz/cross-device-backup-codex-skill.git `
  "$env:USERPROFILE\.codex\skills\codex-relay"
```

Restart or reload Codex after installation.

## Usage

Invoke the skill only inside a project that should participate in cross-device backup:

```text
Use $codex-relay to enable cross-device backup for this project.
```

Codex Relay should then:

1. resolve only the current project and its remote;
2. confirm or prepare the separate private session repository;
3. create missing durable context documents without overwriting existing documentation;
4. create a machine-specific configuration outside the project repository;
5. register a native scheduler for this project only;
6. run a dry run and one real backup;
7. verify that the real branch, worktree, and Git index remain unchanged.

See [`references/setup.md`](references/setup.md) for configuration, scheduling, restoration, and macOS/Windows handoff details.

## Performance model

The recommended schedule is every 5–10 minutes with a 90-second source-idle threshold.

- no model invocation;
- no automatic test suite;
- no branch checkout or stash;
- no new source commit when the snapshot is unchanged;
- a lock prevents overlapping runs;
- failed pushes leave local recovery objects or commits for a later retry;
- active source changes cause the source snapshot to wait rather than compete with the main task.

The initial session export and the first scan of a large repository may take longer. Exclude dependencies, build output, virtual environments, caches, and large generated files through the project's normal ignore rules.

## Context continuity and limits

Session migration can preserve substantial conversational context, but it is not a bit-perfect snapshot of a live process. It cannot guarantee recovery of:

- running terminal processes;
- temporary browser or third-party application state;
- connector data that was returned but never persisted;
- files outside the selected workspace;
- truncated tool output;
- internal session formats that become incompatible with a future Codex version.

Durable context files provide the fallback. They should be updated at meaningful milestones, before a device handoff, and after consequential decisions—not every few minutes—so continuity does not slow the main task with repetitive summarization.

## Security boundaries

Codex Relay never uploads the complete Codex home directory. It must not publish:

```text
~/.codex/auth.json
.env files
SSH private keys
cookies or keychain data
Codex caches, locks, logs, or live SQLite databases
```

Session bundles can still contain prompts, source excerpts, paths, terminal output, or secrets that were printed during a task. A private session repository is the minimum recommended destination. Encryption remains optional when the user knowingly chooses private plaintext storage.

## Testing

Run the temporary-index isolation test:

```bash
python3 scripts/test_backup_project.py
```

The test creates a disposable Git repository and verifies that a recovery snapshot contains tracked, staged, modified, and non-ignored untracked files while leaving the real worktree and index unchanged.

## Status and limitations

- This is an unofficial community skill, not an OpenAI product.
- It relies on `cct` and local Codex session formats, which can change.
- Imports are intentionally not scheduled because they mutate local session state.
- The same project should not be actively edited on two devices without an intentional handoff.
- No backup can preserve data that was never flushed before sudden power loss.

## Contributing

Issues and pull requests are welcome. Contributions should preserve these invariants:

- explicit project-level opt-in;
- no global conversation harvesting;
- no model dependency for scheduled backups;
- no mutation of the user's normal Git state;
- no automatic publication of credentials;
- failed backups preserve the last known-good artifact.

## License

MIT
