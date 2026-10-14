from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import RouteMode, RouteRequest
from .registry import LocalRegistry
from .router import SkillRouter


def main() -> int:
    parser = argparse.ArgumentParser(prog="skill-router")
    parser.add_argument("--skills-dir", action="append", default=["~/.cursor/skills"])
    sub = parser.add_subparsers(dest="command", required=True)

    route = sub.add_parser("route")
    route.add_argument("text")
    route.add_argument("--mode", choices=[mode.value for mode in RouteMode], default="auto")
    route.add_argument("--use", action="append", default=[], dest="explicit_skills")
    route.add_argument("--allow-external-search", action="store_true")
    route.add_argument("--max-skills", type=int, default=3)

    config = sub.add_parser("config")
    config.add_argument("--mode", choices=[mode.value for mode in RouteMode], required=True)

    args = parser.parse_args()
    if args.command == "config":
        print(json.dumps({"mode": args.mode, "message": "请将此模式写入 Agent runtime 配置"}, ensure_ascii=False))
        return 0

    registry = LocalRegistry(args.skills_dir)
    result = SkillRouter(registry).route(RouteRequest(
        text=args.text,
        mode=RouteMode(args.mode),
        explicit_skills=tuple(args.explicit_skills),
        allow_external_search=args.allow_external_search,
        max_skills=args.max_skills,
    ))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

