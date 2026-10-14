from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .config import RouterConfig, default_path, load, save
from .models import RouteMode, RouteRequest
from .registry import HttpRegistry, LocalRegistry
from .router import SkillRouter


def main() -> int:
    parser = argparse.ArgumentParser(prog="skill-router")
    parser.add_argument("--skills-dir", action="append", default=None)
    parser.add_argument("--config-file", default=None)
    parser.add_argument("--registry-url", action="append", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    route = sub.add_parser("route")
    route.add_argument("text")
    route.add_argument("--mode", choices=[mode.value for mode in RouteMode], default=None)
    route.add_argument("--use", action="append", default=[], dest="explicit_skills")
    route.add_argument("--allow-external-search", action="store_true")
    route.add_argument("--max-skills", type=int, default=None)

    config = sub.add_parser("config")
    config.add_argument("--mode", choices=[mode.value for mode in RouteMode])
    config.add_argument("--allow-external-search", action=argparse.BooleanOptionalAction, default=None)
    config.add_argument("--max-skills", type=int, default=None)
    config.add_argument("--registry-url", action="append", default=None)
    sub.add_parser("status")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--external", action="store_true")

    args = parser.parse_args()
    config_path = args.config_file or default_path()
    current = load(config_path)
    if args.command == "config":
        updated = RouterConfig(
            mode=RouteMode(args.mode) if args.mode else current.mode,
            allow_external_search=(
                args.allow_external_search
                if args.allow_external_search is not None
                else current.allow_external_search
            ),
            max_skills=args.max_skills if args.max_skills is not None else current.max_skills,
            registry_urls=tuple(args.registry_url) if args.registry_url is not None else current.registry_urls,
        )
        if updated.max_skills < 1:
            parser.error("--max-skills must be >= 1")
        saved = save(updated, config_path)
        print(json.dumps({"saved": str(saved), **_config_dict(updated)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        print(json.dumps({"config_file": str(config_path), **_config_dict(current)}, ensure_ascii=False, indent=2))
        return 0

    skills_dirs = args.skills_dir or os.environ.get(
        "SKILL_ROUTER_SKILLS_DIR", "~/.codex/skills:~/.cursor/skills"
    ).split(":")
    registry = LocalRegistry(skills_dirs)
    registry_urls = args.registry_url if args.registry_url is not None else list(current.registry_urls)
    external = [HttpRegistry(url) for url in registry_urls]
    if args.command == "search":
        results = [
            {
                "name": skill.name,
                "description": skill.description,
                "source": skill.source,
                "version": skill.version,
                "operations": list(skill.operations),
            }
            for skill in registry.search(args.query)
        ]
        if args.external:
            for remote in external:
                try:
                    matches = remote.search(args.query)
                except Exception:
                    continue
                results.extend(
                    {
                        "name": skill.name,
                        "description": skill.description,
                        "source": skill.source,
                        "version": skill.version,
                        "operations": list(skill.operations),
                    }
                    for skill in matches
                )
        print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False, indent=2))
        return 0
    result = SkillRouter(registry, external).route(RouteRequest(
        text=args.text,
        mode=RouteMode(args.mode) if args.mode else current.mode,
        explicit_skills=tuple(args.explicit_skills),
        allow_external_search=args.allow_external_search or current.allow_external_search,
        max_skills=args.max_skills if args.max_skills is not None else current.max_skills,
    ))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _config_dict(config: RouterConfig) -> dict[str, object]:
    return {
        "mode": config.mode.value,
        "allow_external_search": config.allow_external_search,
        "max_skills": config.max_skills,
        "registry_urls": list(config.registry_urls),
    }


if __name__ == "__main__":
    raise SystemExit(main())

