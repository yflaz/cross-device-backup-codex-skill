# Cross-device Backup for Codex

> 按项目显式启用、不中断任务、在 Codex 用量耗尽后仍能继续运行的跨设备源码与会话备份技能。

Cross-device Backup is an explicit opt-in Codex skill that protects one selected project across macOS and Windows. It combines non-invasive Git recovery snapshots, project-scoped Codex session bundles, and durable context documents while keeping routine backup work outside the model loop.

它解决的不是单纯的“代码怎么同步”，而是三个经常被混在一起的问题：

1. 项目文件如何跨电脑延续；
2. Codex 对话、工具记录和项目上下文如何迁移；
3. 当模型用量归零或任务意外停止时，谁来执行最后一次备份。

## Why this exists / 为什么需要它

Git 很适合保存代码，但普通 Git 提交不会自动保存 Codex 的本地会话。只迁移会话也不够，因为运行环境、未提交源码和项目决策可能已经改变。更关键的是，如果备份依赖 Codex 在任务末尾执行，那么用量耗尽时恰好可能没有最后一次工具调用。

本技能把连续性拆成三层：

| Layer | What it protects | Recovery value |
| --- | --- | --- |
| Source snapshot | 已跟踪及未忽略的项目文件 | 恢复任务中尚未形成正式提交的工作 |
| Session bundle | 项目相关的 Codex rollout、会话元数据和 Git context | 在另一台电脑继续原有对话 |
| Durable context | `AGENTS.md`、项目状态、决策和下一步 | 会话无法恢复时仍能快速重建工作上下文 |

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

## Design principles / 设计原则

### Explicit opt-in, not global collection

技能的调用策略是 `allow_implicit_invocation: false`。它不会自动扫描或登记全部 Codex 项目。只有用户明确调用 `$cross-device-backup`，或明确说明当前项目需要跨设备备份时，才允许配置该项目。

### No interruption of active work

自动源码快照使用临时 Git index，不会：

- 切换当前分支；
- 修改真实暂存区；
- 创建或应用 stash；
- 清理工作目录；
- 停止或重启 Codex；
- 在正常分支中制造大量自动提交。

项目刚发生变化时，后台任务会跳过源码快照并稍后重试。会话包先写入临时文件，只有成功导出后才替换上一份有效备份。

### Backup must survive model exhaustion

定时工作由 macOS `launchd` 或 Windows Task Scheduler 执行。后台脚本不调用模型、不创建 Codex 自动化任务，因此不消耗 context 或模型用量。即使 Codex 无法开始下一轮回复，本机仍能在项目停止变化后完成备份。

### Cross-platform by design

每台电脑使用独立的 `device` 名称和恢复分支。macOS 与 Windows 项目路径不同，通过 `cct` 的工作目录映射在导入时处理，不要求两端目录字符串完全一致。

### Recovery artifacts are not normal commits

自动快照发布到 `refs/heads/codex-backup/<device>`。它是灾难恢复层，不替代结构清晰的正常提交、代码审查和发布分支。

## How it differs / 与同类方案的区别

本项目不是对现有会话工具的重新实现。它使用 [`codex-claude-transfer`](https://github.com/ahmojo/codex-claude-transfer)（`cct`）作为项目级会话导出引擎，并在其上增加 Codex 技能编排和操作系统级容灾。

| Project or approach | Primary focus | Difference in this skill |
| --- | --- | --- |
| [`codex-claude-transfer`](https://github.com/ahmojo/codex-claude-transfer) | 会话导出、导入、路径映射和跨 agent 转换 | 本技能复用它，并补充源码恢复分支、耐久 context、显式项目登记和无模型调度 |
| [`codex-session-sync`](https://github.com/shonngithub/codex-session-sync) | 通过 WebDAV 同步本地 Codex 状态，并管理索引与备份 | 本技能不默认同步整个本地状态，不要求 WebDAV，且把范围限制到用户选中的项目 |
| [`codex-handoff`](https://github.com/Raf4ik/codex-handoff) | 两台设备间加密 GUI 交接 | 本技能是可审查的 Skill + 脚本方案，支持现有 Git 工作流，并不强制加密或专用 GUI |
| Only Git / 仅使用 Git | 源码版本控制 | 本技能同时保存可恢复会话和明确的项目连续性文档 |
| Ask the agent to back up at the end | 简单但依赖最后一轮模型调用 | 本技能把定时执行交给 OS，用量归零后仍可重试 |

最核心的差异是：**project-scoped、explicit-only、source + session + durable context、quota-independent、non-invasive**。

## Repository layout / 仓库结构

```text
cross-device-backup-codex-skill/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   └── setup.md
└── scripts/
    ├── backup_project.py
    └── test_backup_project.py
```

实际使用时建议分开两个远程仓库：

```text
project-repository
├── normal branches
└── codex-backup/<device>          automatic recovery snapshots

codex-session-backups              private strongly recommended
└── projects/<slug>/devices/<device>/codex-all.codexbundle
```

## Requirements / 前置条件

- Codex CLI or Codex Desktop with local sessions;
- Git;
- Python 3.10+;
- [`cct`](https://github.com/ahmojo/codex-claude-transfer), verified with `cct doctor`;
- an existing Git repository for the selected project with at least one normal commit;
- a separate private Git repository for session bundles;
- Git authentication that works without an interactive password prompt for scheduled pushes.

## Installation / 安装

macOS or Linux:

```bash
git clone https://github.com/yflaz/cross-device-backup-codex-skill.git \
  ~/.codex/skills/cross-device-backup
```

Windows PowerShell:

```powershell
git clone https://github.com/yflaz/cross-device-backup-codex-skill.git `
  "$env:USERPROFILE\.codex\skills\cross-device-backup"
```

Restart or reload Codex after installation.

## Usage / 使用方式

English:

```text
Use $cross-device-backup to enable cross-device backup for this project.
```

中文：

```text
使用 $cross-device-backup，为当前项目启用跨设备备份。
```

Codex should then:

1. resolve only the current project and its remote;
2. confirm or create the separate private session repository;
3. create missing durable context documents without overwriting existing ones;
4. install a project-specific configuration outside the repository;
5. register a native scheduler for this project only;
6. run a dry run and a real backup;
7. verify that the real branch, worktree and Git index are unchanged.

Detailed configuration, restore, and macOS/Windows handoff guidance is in [`references/setup.md`](references/setup.md).

## Performance model / 对主任务的影响

The recommended schedule is every 5–10 minutes with a 90-second source idle threshold.

- No model invocation;
- no automatic tests;
- no branch checkout;
- no stash;
- unchanged snapshots produce no new source commit;
- overlapping runs are prevented with a lock;
- failed pushes leave local recovery objects or commits for later retry.

首次会话导出和大型仓库扫描会比增量运行更慢。应通过 `.gitignore` 排除依赖目录、构建产物、虚拟环境、缓存和大型生成文件。

## Context continuity / 上下文连续性

会话迁移可以保留大量可继续使用的对话上下文，但它不是正在运行进程的完整镜像。以下内容不能保证位级恢复：

- 仍在运行的终端进程；
- 浏览器或第三方应用的临时状态；
- 外部连接器当时返回但没有持久化的数据；
- 工作区之外的本地文件；
- 被截断的工具输出；
- 后续 Codex 版本不再兼容的内部会话格式。

因此技能同时维护耐久 context 文档，并要求在里程碑、设备切换和重要决策时更新，而不是每隔几分钟让模型生成冗余总结。

## Security / 安全边界

This skill never uploads the complete Codex home. In particular, it must not publish:

```text
~/.codex/auth.json
.env files
SSH private keys
cookies or keychain data
Codex caches, locks, logs, or live SQLite databases
```

Session bundles may still contain prompts, code, paths, terminal output, or secrets that were printed during a task. A private repository is the minimum recommended destination. Encryption is optional when the user knowingly chooses plaintext private storage.

## Testing / 测试

Run the temporary-index isolation test:

```bash
python3 scripts/test_backup_project.py
```

The test creates a disposable Git repository and verifies that a recovery snapshot contains tracked, staged, modified and non-ignored untracked files while leaving the real worktree and index unchanged.

## Status and limitations

- This is an unofficial community skill, not an OpenAI product.
- It relies on `cct` and Codex local session formats, which can change.
- Imports are intentionally not scheduled because they mutate local session state.
- One project must not be actively edited on two devices without an intentional handoff.
- No backup can preserve bytes that were never flushed before sudden power loss.

## Contributing

Issues and pull requests are welcome. Contributions should preserve these invariants:

- explicit project-level opt-in;
- no global conversation harvesting;
- no model dependency for scheduled backups;
- no mutation of the user's normal Git state;
- no automatic publication of credentials;
- failed backups must preserve the last known-good artifact.

## License

MIT
