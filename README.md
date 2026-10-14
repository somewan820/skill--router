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
python3 -m skill_router.install \
  --destination /path/to/your/agent/skills/skill-router
```

上面的命令只会预览安装文件。确认后再执行：

```bash
python3 -m skill_router.install \
  --destination /path/to/your/agent/skills/skill-router \
  --approve
python3 -m skill_router.verify \
  --path /path/to/your/agent/skills/skill-router
```

## 快速开始

```bash
python -m skill_router.cli --skills-dir ~/.cursor/skills \
  route "请读取这个飞书文档并提取待办：https://example.com/docx/abc"
```

设置模式：

```bash
python -m skill_router.cli config --mode manual
python -m skill_router.cli config --mode off
python -m skill_router.cli config --mode auto
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
---
```

## 安全默认值

- 本地 Skill 优先；
- 外部搜索是可插拔能力，默认关闭；
- 外部 Skill 只允许被发现，不自动安装；
- 低置信度不自动加载；
- `manual` 模式只接受用户显式指定的 Skill；
- `off` 模式不自动路由。

## 下一步

1. 增加真正的远程 Registry adapter（例如 `skills.sh`）。
2. 为外部 Skill 增加来源、版本、checksum 和用户确认安装流程。
3. 将 `SkillRouter` 接入具体 Agent runtime 或 hook。

