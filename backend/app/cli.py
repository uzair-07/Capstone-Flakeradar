"""Admin commands for the server operator.

    python -m app.cli create-project --name "Demo" [--slug demo] [--owner you@example.com] [--json]
    python -m app.cli create-token --project demo [--name ci] [--json]
    python -m app.cli claim-projects --owner you@example.com   # give ownerless projects an owner
    python -m app.cli recompute-stats --project demo           # rebuild flakiness scores
"""

import argparse
import json
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.service import recompute_project
from app.auth.service import normalise_email
from app.db.session import session_scope
from app.models import Project, User
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
            if args.owner:
                project.owner_id = _user(db, args.owner).id
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


def _user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == normalise_email(email)))
    if user is None:
        raise ValueError(f"No account for {email}. Register in the web app first.")
    return user


def cmd_claim_projects(args: argparse.Namespace) -> int:
    with session_scope() as db:
        try:
            owner = _user(db, args.owner)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        projects = list(db.scalars(select(Project).where(Project.owner_id.is_(None))))
        for project in projects:
            project.owner_id = owner.id
        db.commit()
        print(f"{len(projects)} project(s) now owned by {owner.email}")
    return 0


def cmd_recompute_stats(args: argparse.Namespace) -> int:
    with session_scope() as db:
        try:
            project = get_project_by_slug(db, args.project)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        count = recompute_project(db, project)
        db.commit()
        print(f"Recomputed scores for {count} test(s) in {project.slug}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="FlakeRadar admin")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-project", help="Create a project and its first CI token")
    p.add_argument("--name", required=True)
    p.add_argument("--slug", help="URL name; derived from --name if omitted")
    p.add_argument("--owner", help="Email of an existing account that will own the project")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    p.set_defaults(func=cmd_create_project)

    t = sub.add_parser("create-token", help="Create another API token for a project")
    t.add_argument("--project", required=True, help="Project slug")
    t.add_argument("--name", default="ci")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_create_token)

    c = sub.add_parser("claim-projects", help="Assign every ownerless project to an account")
    c.add_argument("--owner", required=True, help="Account email")
    c.set_defaults(func=cmd_claim_projects)

    r = sub.add_parser("recompute-stats", help="Rebuild flakiness scores for a project")
    r.add_argument("--project", required=True, help="Project slug")
    r.set_defaults(func=cmd_recompute_stats)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
