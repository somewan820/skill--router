# Skill Router

一个可通过仓库链接分发、由其他 Agent 自行检查并安装的 Agent Skill 包，同时提供本地优先路由器。它根据用户请求识别领域、资源类型和操作，推荐或生成一个可执行的 Skill 组合计划。

当前版本包含：

- 本地 `SKILL.md` 扫描和元数据注册；
- `auto`、`manual`、`off` 三种路由模式；
- 基于领域、资源类型、操作和触发词的可解释评分；
- 多 Skill 组合计划与依赖顺序；
- 外部 Registry 的稳定适配器接口（默认不会联网或自动安装）；
- JSON CLI，方便被 Agent、Hook 或其他运行时调用。
- `skill.json`、`INSTALL.md` 和验证/安装命令，方便任意支持 Markdown Skill 的 Agent 自安装。

## 从仓库链接安装

把仓库链接交给你的 Agent，并要求它先阅读 `skill.json`、`SKILL.md` 和 `INSTALL.md`，确认权限后安装。Agent 应该根据自己的 Skill 目录提供安装目标；本仓库不假设 Codex、Claude、Cursor 或其他具体产品的目录。

如果在仓库根目录手动执行参考安装器：

```bash
npm install
npm run build
node dist/cli.js install \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router"
```

上面的命令只会预览安装文件。确认后再执行：

```bash
node dist/cli.js install \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router" \
  --approve
node dist/cli.js verify \
  --path "$AGENT_SKILL_DIRECTORY/skill-router"
```

更新时使用同一个安装命令即可；安装器会覆盖它自己管理的文件，并保留目标目录中的用户文件：

```bash
node dist/cli.js install \
  --source . \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router" \
  --approve
```

卸载前先预览：

```bash
node dist/cli.js uninstall \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router"
```

确认卸载：

```bash
node dist/cli.js uninstall \
  --destination "$AGENT_SKILL_DIRECTORY/skill-router" \
  --approve
```

## 快速开始

```bash
node dist/cli.js --skills-dir ~/.cursor/skills \
  route "请读取这个飞书文档并提取待办：https://your-document-host/docx/abc"
```

设置模式：

```bash
node dist/cli.js config --mode manual
node dist/cli.js config --mode off
node dist/cli.js config --mode auto
node dist/cli.js status
```

配置默认保存到 `~/.config/skill-router/config.json`。也可以通过 `--config-file` 或 `SKILL_ROUTER_CONFIG` 指定其他配置文件。

配置外部搜索和最大 Skill 数量：

```bash
node dist/cli.js config \
  --mode auto \
  --allow-external-search \
  --max-skills 3
```

配置通用远程 Registry：

```bash
node dist/cli.js config \
  --registry-url https://registry.example.com/skills
```

查询本地 Skill：

```bash
node dist/cli.js search "代码审查"
```

查询已配置的远程 Registry：

```bash
node dist/cli.js \
  --registry-url https://registry.example.com/skills \
  search --external "database migration"
```

远程 Registry 只负责返回候选元数据，不会因为搜索结果自动安装 Skill。

## 语义路由 Provider

如果本地 Skill 只有自然语言描述、没有足够的结构化触发词，可以把宿主 Agent 的模型接入为通用语义 Provider：

```bash
node dist/cli.js route \
  --semantic \
  --semantic-command 'your-agent-semantic-provider' \
  "请从这个 GitHub 仓库安装一个 Skill"
```

Provider 从 stdin 接收：

```json
{
  "task": "用户任务",
  "candidates": [
    {
      "name": "skill-installer",
      "description": "Install skills from a GitHub repository"
    }
  ]
}
```

并向 stdout 返回：

```json
{
  "selections": [
    {
      "name": "skill-installer",
      "confidence": 0.97,
      "reason": "任务要求从 GitHub 仓库安装 Skill"
    }
  ]
}
```

Router 不绑定模型供应商；Provider 由当前 Agent 决定。模型选择仍会经过本地 Skill 白名单、置信度、排他组和依赖检查。

语义结果的决策阈值：

```text
confidence >= 0.85：自动加载
0.60 <= confidence < 0.85：返回 confirm，等待用户确认
confidence < 0.60：拒绝自动加载
```

语义 Provider 只能参与本地 Skill 选择，不能绕过外部 Skill 的安装确认。

## 记录真实反馈

用户可以把一次路由纠正记录下来，默认写入本地：

```bash
node dist/cli.js feedback \
  --task "请从 GitHub 仓库安装一个 Skill" \
  --selected code-review \
  --corrected skill-installer
```

如果选择正确：

```bash
node dist/cli.js feedback \
  --task "请运行测试并分析失败" \
  --selected test-runner \
  --accepted
```

反馈文件默认是 `~/.config/skill-router/feedback.jsonl`，也可以用 `--feedback-file` 指定路径。反馈只在本地保存，后续可用于生成回归任务、改进 Skill 元数据或评估路由质量。

单次请求可以覆盖持久化配置：

```bash
node dist/cli.js route \
  --mode off \
  "这次不要自动选择 Skill"
```

读取结果：

```json
{
  "mode": "auto",
  "action": "route",
  "selected": ["lark-doc", "lark-task"],
  "confidence": 0.94,
  "reason": "检测到 feishu/cloud_document/read, extract_action_items",
  "external_search": false,
  "install_required": false
}
```

## Skill 元数据

现有 `SKILL.md` 的 `name` 和 `description` 足以工作。为了提高路由准确率，可以在 frontmatter 增加结构化字段：

```yaml
---
name: lark-doc
description: 读取和编辑飞书云文档正文
domains: [feishu]
resource_types: [cloud_document]
operations: [read, create, edit]
triggers: [飞书文档, docx, doubao.com/docx]
not_for: [file_permission, file_move]
related_skills: [lark-drive, lark-task]
exclusive_group: document-reader
priority: 10
---
```

`triggers` 应包含用户实际可能使用的词，可以同时声明多语言触发词。Router 不在核心代码中内置任何具体领域或 Skill 名称的同义词。

当多个 Skill 提供互斥的同类能力时，可以声明相同的 `exclusive_group`，路由器会保留得分最高的一个。需要串联的 Skill 使用 `dependencies`；可以同时协作的 Skill 不要放入同一个排他组。

## 安全默认值

- 本地 Skill 优先；
- 外部搜索是可插拔能力，默认关闭；
- 外部 Skill 只允许被发现，不自动安装；
- 低置信度不自动加载；
- `manual` 模式只接受用户显式指定的 Skill；
- `off` 模式不自动路由。

## 通用远程 Registry 协议

Registry URL 接受一个 `q` 查询参数，并返回以下任一 JSON 结构：

```json
{
  "skills": [
    {
      "name": "example-skill",
      "description": "Does a specialized task",
      "version": "1.0.0",
      "domains": ["example"],
      "resource_types": ["artifact"],
      "operations": ["inspect"],
      "triggers": ["inspect", "检查"],
      "dependencies": [],
      "exclusive_group": null,
      "priority": 0
    }
  ]
}
```

也可以直接返回数组。Registry 不负责安装；安装必须经过独立的包验证和用户确认流程。

## 下一步

1. 增加真正的远程 Registry adapter（例如 `skills.sh`）。
2. 为外部 Skill 增加来源、版本、checksum 和用户确认安装流程。
3. 将 `SkillRouter` 接入具体 Agent runtime 或 hook。

## 收益评估

运行可复现的本地路由基准：

```bash
npm run evaluate
```

基准数据位于 `evaluation/tasks.json`，运行器位于 `evaluation/benchmark.mjs`。它对比：

- `control`：不选择任何 Skill 的路由基线；
- `treatment`：启用 Skill Router 的结果。

输出指标包括 Precision、Recall、F1、Exact Plan Accuracy、无 Skill 任务准确率、平均/P95 路由延迟，以及固定种子的 bootstrap 95% F1 区间。这个基准只衡量路由质量，不等价于真实 Agent 的任务完成时间或成本收益；生产结论需要使用相同任务分布做 Agent A/B 测试。

真实环境测试结果保存在 `evaluation/real-results.json`，对应任务集为 `evaluation/real-tasks.json`。该测试直接读取运行机器的实际 Skill 目录，因此结果会随已安装 Skill 和其描述变化，不应与合成基准混合比较。

