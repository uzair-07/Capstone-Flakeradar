"""Admin commands until the web UI has account management (Sprint 2).

    python -m app.cli create-project --name "Demo" [--slug demo] [--json]
    python -m app.cli create-token --project demo [--name ci] [--json]
"""

import argparse
import json
import sys

from app.db.session import session_scope
from app.projects.service import create_project, create_token, get_project_by_slug


def _print(payload: dict[str, str], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload))
        return
    for key, value in payload.items():
        print(f"{key:>8}: {value}")
    if "token" in payload:
        print("\nStore the token now (e.g. as the FLAKERADAR_TOKEN CI secret).")
        print("It is not shown again.")


def cmd_create_project(args: argparse.Namespace) -> int:
    with session_scope() as db:
        try:
            project = create_project(db, args.name, args.slug)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        token = create_token(db, project, "ci")
        db.commit()
        _print({"project": project.slug, "token": token.value}, args.json)
    return 0


def cmd_create_token(args: argparse.Namespace) -> int:
    with session_scope() as db:
        try:
            project = get_project_by_slug(db, args.project)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        token = create_token(db, project, args.name)
        db.commit()
        _print({"project": project.slug, "token": token.value}, args.json)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="FlakeRadar admin")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-project", help="Create a project and its first CI token")
    p.add_argument("--name", required=True)
    p.add_argument("--slug", help="URL name; derived from --name if omitted")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    p.set_defaults(func=cmd_create_project)

    t = sub.add_parser("create-token", help="Create another API token for a project")
    t.add_argument("--project", required=True, help="Project slug")
    t.add_argument("--name", default="ci")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_create_token)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
