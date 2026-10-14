import tempfile
import unittest
from pathlib import Path

from skill_router.models import RouteMode, RouteRequest
from skill_router.registry import LocalRegistry
from skill_router.router import SkillRouter
from skill_router.install import install
from skill_router.verify import verify


def write_skill(root: Path, name: str, body: str) -> None:
    path = root / name
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(body, encoding="utf-8")


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        write_skill(root, "lark-doc", """---
name: lark-doc
description: 读取和编辑飞书云文档正文
domains: [feishu]
resource_types: [cloud_document]
operations: [read, edit]
triggers: [飞书文档, docx, doubao.com/docx]
---
# doc
""")
        write_skill(root, "lark-task", """---
name: lark-task
description: 创建飞书任务和待办
domains: [feishu]
operations: [create_task]
triggers: [待办, 行动项, 任务]
---
# task
""")
        self.router = SkillRouter(LocalRegistry([root]))

    def tearDown(self):
        self.temp.cleanup()

    def test_local_route_composes_document_and_tasks(self):
        result = self.router.route(RouteRequest("读取这个飞书文档并提取行动项：https://x/doubao.com/docx/a"))
        self.assertEqual(result.action, "load")
        self.assertEqual(result.selected[0].name, "lark-doc")
        self.assertIn("lark-task", [item.name for item in result.selected])

    def test_off_does_not_route(self):
        result = self.router.route(RouteRequest("读取飞书文档", mode=RouteMode.OFF))
        self.assertEqual(result.action, "skip")
        self.assertEqual(result.selected, [])

    def test_manual_only_uses_explicit_skills(self):
        result = self.router.route(RouteRequest(
            "读取飞书文档并创建任务",
            mode=RouteMode.MANUAL,
            explicit_skills=("lark-task",),
        ))
        self.assertEqual([item.name for item in result.selected], ["lark-task"])

    def test_no_match_can_request_external_search(self):
        result = self.router.route(RouteRequest(
            "设计一个完全未知的内部系统",
            allow_external_search=True,
        ))
        self.assertEqual(result.action, "external_search")
        self.assertTrue(result.external_search)

    def test_chinese_development_intent_routes_to_review_and_linear(self):
        root = Path(self.temp.name) / "development-skills"
        write_skill(root, "code-review", """---
name: code-review
description: Review code changes for security, regression, compatibility, and correctness
operations: [review]
triggers: [code review, pull request, diff, security, regression, compatibility]
---
# review
""")
        write_skill(root, "linear", """---
name: linear
description: Create and update Linear issues, tickets, and projects
operations: [create_issue]
triggers: [Linear, issue, ticket, project]
---
# linear
""")
        write_skill(root, "simplify-codebase", """---
name: simplify-codebase
description: Simplification audit for deleting dead code and reducing accidental complexity
operations: [simplify]
triggers: [simplify, dead code, entropy]
---
# simplify
""")
        result = SkillRouter(LocalRegistry([root])).route(RouteRequest(
            "请审查当前分支的代码变更，检查安全性和回归风险；"
            "把问题创建成 Linear 工单并关联到当前项目。",
        ))
        self.assertEqual(result.action, "load")
        self.assertEqual({item.name for item in result.selected}, {"code-review", "linear"})

    def test_skill_package_manifest_is_valid(self):
        root = Path(__file__).parents[1]
        self.assertEqual(verify(root), [])

    def test_installer_previews_then_copies_after_approval(self):
        source = Path(__file__).parents[1]
        destination = Path(self.temp.name) / "installed" / "skill-router"
        preview = install(source, destination)
        self.assertTrue(preview["requires_confirmation"])
        result = install(source, destination, approve=True)
        self.assertTrue(result["installed"])
        self.assertEqual(verify(destination), [])


if __name__ == "__main__":
    unittest.main()

