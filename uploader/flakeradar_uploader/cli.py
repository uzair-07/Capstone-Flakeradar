"""flakeradar-upload: send JUnit XML reports from a CI job to a FlakeRadar server.

Uses only the Python standard library so it runs on any CI image with Python 3.10+.

By default a failed upload prints a warning and exits 0, so FlakeRadar being down never
breaks your build. Pass --fail-on-error to change that.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from flakeradar_uploader import __version__

USER_AGENT = f"flakeradar-uploader/{__version__}"
TERMINAL = {"done", "failed"}


class UploadError(Exception):
    pass


@dataclass(frozen=True)
class CiMetadata:
    commit_sha: str | None
    branch: str | None
    ci_run_id: str | None
    attempt: int


def detect_ci_metadata(env: Mapping[str, str]) -> CiMetadata:
    """Read commit, branch and run details from common CI environment variables."""
    if env.get("GITHUB_ACTIONS") == "true":
        branch = env.get("GITHUB_HEAD_REF") or env.get("GITHUB_REF_NAME")
        return CiMetadata(
            commit_sha=env.get("GITHUB_SHA"),
            branch=branch,
            ci_run_id=env.get("GITHUB_RUN_ID"),
            attempt=_int(env.get("GITHUB_RUN_ATTEMPT"), 1),
        )
    if env.get("GITLAB_CI") == "true":
        return CiMetadata(
            commit_sha=env.get("CI_COMMIT_SHA"),
            branch=env.get("CI_COMMIT_REF_NAME"),
            ci_run_id=env.get("CI_PIPELINE_ID"),
            attempt=1,
        )
    return CiMetadata(commit_sha=None, branch=None, ci_run_id=None, attempt=1)


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except ValueError:
        return default


def expand_paths(patterns: Iterable[str]) -> list[str]:
    """Expand globs ourselves: Windows shells and some CI runners do not."""
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern, recursive=True))
        paths.extend(matches if matches else [pattern])
    return list(dict.fromkeys(paths))  # drop duplicates, keep order


def encode_multipart(
    fields: Mapping[str, str], file_field: str, filename: str, content: bytes
) -> tuple[bytes, str]:
    boundary = f"----flakeradar{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"'.encode(),
            b"",
            value.encode(),
        ]
    safe_name = os.path.basename(filename).replace('"', "")
    lines += [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="{file_field}"; filename="{safe_name}"'.encode(),
        b"Content-Type: application/xml",
        b"",
        content,
        f"--{boundary}--".encode(),
        b"",
    ]
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def _request(
    method: str, url: str, token: str, body: bytes | None = None, content_type: str | None = None
) -> dict[str, object]:
    headers = {"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except (ValueError, AttributeError):
            pass
        raise UploadError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise UploadError(f"Cannot reach {url}: {exc.reason}") from exc


def upload_file(
    server: str, project: str, token: str, path: str, meta: CiMetadata
) -> dict[str, object]:
    try:
        with open(path, "rb") as handle:
            content = handle.read()
    except OSError as exc:
        raise UploadError(f"Cannot read {path}: {exc.strerror}") from exc

    fields = {"attempt": str(meta.attempt)}
    for key in ("commit_sha", "branch", "ci_run_id"):
        value = getattr(meta, key)
        if value:
            fields[key] = value
    body, content_type = encode_multipart(fields, "file", path, content)
    url = f"{server.rstrip('/')}/api/v1/projects/{project}/uploads"
    return _request("POST", url, token, body, content_type)


def wait_for(server: str, token: str, upload_id: str, timeout: float) -> dict[str, object]:
    url = f"{server.rstrip('/')}/api/v1/uploads/{upload_id}"
    deadline = time.monotonic() + timeout
    delay = 0.5
    while True:
        status = _request("GET", url, token)
        if status.get("status") in TERMINAL or time.monotonic() >= deadline:
            return status
        time.sleep(delay)
        delay = min(delay * 2, 5)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flakeradar-upload",
        description="Upload JUnit XML test reports to FlakeRadar.",
    )
    parser.add_argument("reports", nargs="+", help="Report files or glob patterns")
    parser.add_argument("--server", default=os.environ.get("FLAKERADAR_URL"),
                        help="FlakeRadar base URL (env FLAKERADAR_URL)")
    parser.add_argument("--project", default=os.environ.get("FLAKERADAR_PROJECT"),
                        help="Project slug (env FLAKERADAR_PROJECT)")
    parser.add_argument("--token", default=os.environ.get("FLAKERADAR_TOKEN"),
                        help="Project API token (env FLAKERADAR_TOKEN)")
    parser.add_argument("--commit", help="Commit SHA (detected on GitHub Actions and GitLab CI)")
    parser.add_argument("--branch", help="Branch name (detected on GitHub Actions and GitLab CI)")
    parser.add_argument("--ci-run-id", help="CI run identifier (detected on supported CI)")
    parser.add_argument("--attempt", type=int, help="Attempt number of a re-run job")
    parser.add_argument("--wait", action="store_true", help="Wait until each report is processed")
    parser.add_argument("--wait-timeout", type=float, default=60, help="Seconds to wait (60)")
    parser.add_argument("--fail-on-error", action="store_true",
                        help="Exit 1 if any upload fails (default: warn and exit 0)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    env = os.environ if env is None else env

    missing = [name for name in ("server", "project", "token") if not getattr(args, name)]
    if missing:
        print(f"error: missing --{', --'.join(missing)} (or the FLAKERADAR_* environment "
              "variables)", file=sys.stderr)
        return 2

    detected = detect_ci_metadata(env)
    meta = CiMetadata(
        commit_sha=args.commit or detected.commit_sha,
        branch=args.branch or detected.branch,
        ci_run_id=args.ci_run_id or detected.ci_run_id,
        attempt=args.attempt or detected.attempt,
    )

    errors = 0
    for path in expand_paths(args.reports):
        try:
            result = upload_file(args.server, args.project, args.token, path, meta)
            note = " (already uploaded)" if result.get("duplicate") else ""
            print(f"uploaded {path} -> upload {result.get('id')}{note}")
            if args.wait:
                final = wait_for(args.server, args.token, str(result["id"]), args.wait_timeout)
                print(f"  status: {final.get('status')}"
                      + (f" ({final.get('error')})" if final.get("error") else ""))
                if final.get("status") == "failed":
                    errors += 1
        except UploadError as exc:
            errors += 1
            print(f"warning: {path}: {exc}", file=sys.stderr)

    if errors and args.fail_on_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
