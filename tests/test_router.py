import tempfile
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

from skill_router.models import RouteMode, RouteRequest
from skill_router.models import SkillMetadata
from skill_router.registry import HttpRegistry, LocalRegistry
from skill_router.router import SkillRouter
from skill_router.install import INSTALL_RECORD, install, uninstall
from skill_router.verify import verify
from skill_router.config import RouterConfig, load, save


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

    def test_external_registry_candidates_are_returned_without_installing(self):
        class FakeRegistry:
            name = "test-registry"

            def search(self, query):
                return [
                    SkillMetadata(
                        "remote-tool",
                        "A remote tool",
                        source=self.name,
                        version="2.0.0",
                        operations=("inspect",),
                    )
                ]

        result = SkillRouter(
            LocalRegistry([Path(self.temp.name) / "empty"]),
            [FakeRegistry()],
        ).route(RouteRequest("inspect an unknown artifact", allow_external_search=True))
        self.assertEqual(result.action, "external_candidates")
        self.assertEqual(result.external_candidates[0]["name"], "remote-tool")
        self.assertFalse(result.install_required)

    def test_http_registry_parses_standard_json_response(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"skills":[{"name":"remote-tool","description":"Inspect artifacts","operations":["inspect"]}]}')

            def log_message(self, *_):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            registry = HttpRegistry(f"http://127.0.0.1:{server.server_port}/search")
            skills = registry.search("inspect")
            self.assertEqual(skills[0].name, "remote-tool")
            self.assertTrue(skills[0].source.startswith("127.0.0.1:"))
        finally:
            server.shutdown()
            thread.join()
            server.server_close()

    def test_chinese_development_intent_routes_to_review_and_linear(self):
        root = Path(self.temp.name) / "development-skills"
        write_skill(root, "code-review", """---
name: code-review
description: Review code changes for security, regression, compatibility, and correctness
operations: [review]
triggers: [审查, 代码审查, 代码评审, code review, pull request, diff, security, regression, compatibility]
---
# review
""")
        write_skill(root, "linear", """---
name: linear
description: Create and update Linear issues, tickets, and projects
operations: [create_issue]
triggers: [Linear, 工单, 问题, 项目, issue, ticket, project]
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

    def test_router_config_persists_mode_and_limits(self):
        path = Path(self.temp.name) / "config.json"
        save(RouterConfig(RouteMode.MANUAL, True, 5), path)
        self.assertEqual(load(path), RouterConfig(RouteMode.MANUAL, True, 5))

    def test_dependencies_are_recursively_ordered_before_dependents(self):
        root = Path(self.temp.name) / "dependency-skills"
        write_skill(root, "renderer", """---
name: renderer
description: Render a final artifact
operations: [render]
triggers: [render]
dependencies: [data-source]
---
# renderer
""")
        write_skill(root, "data-source", """---
name: data-source
description: Load and normalize source data
operations: [load]
triggers: [data]
dependencies: [credential-provider]
---
# data
""")
        write_skill(root, "credential-provider", """---
name: credential-provider
description: Resolve credentials for a connected service
operations: [authenticate]
triggers: [credentials]
---
# credentials
""")
        result = SkillRouter(LocalRegistry([root])).route(
            RouteRequest("render data with credentials", max_skills=3)
        )
        self.assertEqual(
            [item.name for item in result.selected],
            ["credential-provider", "data-source", "renderer"],
        )

    def test_dependency_cycles_are_reported_as_warnings(self):
        root = Path(self.temp.name) / "cyclic-skills"
        write_skill(root, "alpha", """---
name: alpha
description: Alpha processing
triggers: [alpha]
dependencies: [beta]
---
# alpha
""")
        write_skill(root, "beta", """---
name: beta
description: Beta processing
triggers: [beta]
dependencies: [alpha]
---
# beta
""")
        result = SkillRouter(LocalRegistry([root])).route(
            RouteRequest("run alpha and beta", max_skills=2)
        )
        self.assertTrue(any("依赖环" in warning for warning in result.warnings))

    def test_installer_previews_then_copies_after_approval(self):
        source = Path(__file__).parents[1]
        destination = Path(self.temp.name) / "installed" / "skill-router"
        preview = install(source, destination)
        self.assertTrue(preview["requires_confirmation"])
        result = install(source, destination, approve=True)
        self.assertTrue(result["installed"])
        self.assertEqual(verify(destination), [])

    def test_uninstall_only_removes_files_managed_by_installer(self):
        source = Path(__file__).parents[1]
        destination = Path(self.temp.name) / "installed" / "skill-router"
        install(source, destination, approve=True)
        user_file = destination / "user-data.txt"
        user_file.write_text("preserve me", encoding="utf-8")
        preview = uninstall(destination)
        self.assertTrue(preview["requires_confirmation"])
        result = uninstall(destination, approve=True)
        self.assertTrue(result["uninstalled"])
        self.assertTrue(user_file.is_file())
        self.assertFalse((destination / INSTALL_RECORD).exists())


if __name__ == "__main__":
    unittest.main()

