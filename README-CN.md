# Codex Relay

Codex Relay 是一个显式启用的 Codex Skill，用于在不中断当前工作的情况下，将选定项目安全地延续到另一台电脑。它通过操作系统原生调度，同时保护源码变更、项目级 Codex 会话和耐久工作上下文；即使模型用量耗尽，备份仍可继续执行。

## 要解决的问题

在两台电脑上使用同一个账号，并不能保证本地 Codex 项目和对话自动互通。Git 只能解决其中一部分：

1. 项目文件需要能在另一台电脑恢复；
2. Codex 对话和会话元数据需要随项目迁移；
3. 即使会话导出不完整，决策和准确的继续位置也需要保留；
4. 最后一次备份不能依赖下一轮模型调用，因为此时用量可能已经耗尽。

Codex Relay 将这些问题拆分为不同的耐久层，而不是假设单一同步机制能够保留所有状态。

## 三层连续性模型

| 层级 | 保护内容 | 存储位置 |
| --- | --- | --- |
| 源码快照 | 已跟踪和未忽略的项目文件，包括尚未完成的变更 | 现有项目远程仓库中的 `codex-backup/<device>` |
| 会话包 | 项目级 Codex 对话、rollout 数据、元数据和 Git context | 独立的私有会话仓库 |
| 耐久上下文 | 稳定指令、已验证状态、决策、阻塞项和下一步 | `AGENTS.md` 及 `docs/` 下的专项文件 |

```text
显式选择项目
      |
      v
操作系统原生调度器  ---- 不调用模型 / 不消耗 Codex 用量
      |
      +---- 临时 Git index ----> codex-backup/<device>
      |
      +---- cct 项目导出 ------> 私有会话仓库
      |
      `---- 里程碑上下文 ------> AGENTS.md + docs/
```

## Codex Relay 的不同之处

### 按项目管理，并且只允许显式启用

Skill 设置了 `allow_implicit_invocation: false`。它不会扫描或登记所有 Codex 项目。只有用户明确调用 `$codex-relay`，或清楚说明当前项目需要跨设备连续性时，才会配置该项目。

### 不依赖模型可用性

定时备份由 macOS `launchd` 或 Windows Task Scheduler 执行。运行脚本不调用模型，也不创建 Codex 定时任务，因此即使对话因模型用量耗尽而无法继续，它仍然可以重试备份。

### 非侵入式 Git 快照

源码快照使用临时 Git index。运行脚本不会切换分支、修改真实暂存区、创建或应用 stash、清理工作树、停止 Codex，也不会把自动提交写入项目的正常分支历史。

### 不只是导出对话

会话包很有价值，但它不是运行中电脑的完整镜像。Codex Relay 还会维护少量耐久上下文文档。当原生会话导入不可用或不完整时，新任务仍可恢复已验证状态和计划中的下一步。

### 跨平台交接

每台设备都有独立的设备名称、恢复分支和会话包路径。macOS 与 Windows 的项目路径可以不同；路径协调只在有意执行导入时发生，不会就地改写已保存的会话包。

## 与相关方案的比较

Codex Relay 不会重新实现会话格式。它使用 [`codex-claude-transfer`](https://github.com/ahmojo/codex-claude-transfer)（`cct`）作为项目级导出和导入引擎，并在其上增加源码恢复、耐久上下文、显式项目登记和不依赖模型用量的调度。

| 项目或方案 | 主要用途 | Codex Relay 的补充或差异 |
| --- | --- | --- |
| [`codex-claude-transfer`](https://github.com/ahmojo/codex-claude-transfer) | 会话导出与导入、路径映射和 agent 转换 | 增加源码恢复分支、耐久上下文、显式项目登记和原生调度 |
| [`codex-session-sync`](https://github.com/shonngithub/codex-session-sync) | 通过 WebDAV 同步范围更广的本地 Codex 状态 | 仅限选定项目、不要求 WebDAV，也不默认收集完整本地状态 |
| [`codex-handoff`](https://github.com/Raf4ik/codex-handoff) | 设备之间的加密 GUI 交接 | 提供可审查的 Skill 加脚本流程，兼容现有 Git 仓库且不要求专用 GUI |
| 仅使用 Git | 源码版本控制 | 增加可恢复的 Codex 会话和明确的连续性文档 |
| 由 agent 在任务结束时备份 | 简单的最后一次模型操作 | 使用原生调度，即使无法执行最后一次模型操作也能运行 |

它的关键组合是：**仅显式启用、按项目管理、源码 + 会话 + 耐久上下文、不依赖模型用量、非侵入式**。

## 仓库结构

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

推荐的实际运行结构使用两个远程仓库：

```text
项目仓库
├── 正常分支
└── codex-backup/<device>          自动恢复快照

私有会话仓库
└── projects/<slug>/devices/<device>/codex-all.codexbundle
```

## 前置条件

- 带本地会话的 Codex CLI 或 Codex Desktop；
- Git；
- Python 3.10 或更高版本；
- [`cct`](https://github.com/ahmojo/codex-claude-transfer)，并通过 `cct doctor` 验证；
- 选定项目已经是 Git 仓库，并且至少有一个正常提交；
- 用于保存会话包的独立私有 Git 仓库；
- 定时推送所需的非交互式 Git 身份验证。

## 安装

macOS 或 Linux：

```bash
git clone https://github.com/yflaz/cross-device-backup-codex-skill.git \
  ~/.codex/skills/codex-relay
```

Windows PowerShell：

```powershell
git clone https://github.com/yflaz/cross-device-backup-codex-skill.git `
  "$env:USERPROFILE\.codex\skills\codex-relay"
```

安装后重新启动或重新加载 Codex。

## 使用方法

仅在需要参与跨设备备份的项目中调用：

```text
使用 $codex-relay，为当前项目启用跨设备备份。
```

Codex Relay 随后应当：

1. 只解析当前项目及其远程仓库；
2. 确认或准备独立的私有会话仓库；
3. 创建缺少的耐久上下文文档，并且不覆盖现有文档；
4. 在项目仓库之外创建当前电脑专用的配置；
5. 只为当前项目注册操作系统原生调度任务；
6. 执行一次 dry run 和一次真实备份；
7. 验证真实分支、工作树和 Git index 均未改变。

配置、调度、恢复以及 macOS/Windows 交接细节请参阅 [`references/setup.md`](references/setup.md)。

## 性能模型

推荐每 5–10 分钟运行一次，并设置 90 秒的源码空闲阈值。

- 不调用模型；
- 不自动运行测试套件；
- 不切换分支或使用 stash；
- 快照无变化时不创建新的源码提交；
- 使用锁避免重叠运行；
- 推送失败时保留本地恢复对象或提交，供之后重试；
- 源码正在变化时等待，不与主任务争抢资源。

首次会话导出和大型仓库的首次扫描可能耗时更长。应通过项目的正常忽略规则排除依赖、构建产物、虚拟环境、缓存和大型生成文件。

## 上下文连续性与限制

会话迁移可以保留大量对话上下文，但它并不是运行中进程的位级快照。它不能保证恢复：

- 正在运行的终端进程；
- 浏览器或第三方应用的临时状态；
- 已返回但从未持久化的 connector 数据；
- 所选工作区之外的文件；
- 被截断的工具输出；
- 与未来 Codex 版本不兼容的内部会话格式。

耐久上下文文件提供后备方案。它们应在重要里程碑、设备交接前以及关键决策后更新，而不是每隔几分钟更新，从而避免重复总结拖慢主任务。

## 安全边界

Codex Relay 绝不会上传完整的 Codex 主目录，尤其不能发布：

```text
~/.codex/auth.json
.env 文件
SSH 私钥
cookie 或 keychain 数据
Codex 缓存、锁、日志或运行中的 SQLite 数据库
```

会话包仍可能包含 prompt、源码片段、路径、终端输出，或者任务中曾打印出来的 secret。私有会话仓库是最低建议。用户明确知情并选择私有明文存储时，加密仍为可选项。

## 测试

运行临时 Git index 隔离测试：

```bash
python3 scripts/test_backup_project.py
```

测试会创建一个一次性 Git 仓库，并验证恢复快照包含已跟踪、已暂存、已修改和未忽略的未跟踪文件，同时真实工作树和 Git index 保持不变。

## 状态与限制

- 这是非官方社区 Skill，不是 OpenAI 产品；
- 它依赖 `cct` 和本地 Codex 会话格式，这些格式可能变化；
- 导入会改变本地会话状态，因此不会被定时执行；
- 未经有意交接，不应在两台设备上同时编辑同一个项目；
- 突然断电前从未写入磁盘的数据无法被任何备份保留。

## 贡献

欢迎提交 Issue 和 Pull Request。贡献内容应保持以下不变量：

- 按项目显式启用；
- 不收集所有对话；
- 定时备份不依赖模型；
- 不改变用户的正常 Git 状态；
- 不自动发布凭据；
- 备份失败时保留上一个有效产物。

## 许可证

MIT
