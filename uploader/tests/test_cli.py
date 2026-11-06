import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from flakeradar_uploader.cli import detect_ci_metadata, encode_multipart, expand_paths, main

REPORT = b'<testsuite name="s"><testcase classname="c" name="t"/></testsuite>'


class FakeServer:
    """A tiny FlakeRadar stand-in that records requests."""

    def __init__(self, upload_status=202, upload_body=None):
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                body = self.rfile.read(length)
                outer.requests.append(("POST", self.path, dict(self.headers), body))
                self._reply(upload_status, upload_body or {"id": "u1", "status": "received"})

            def do_GET(self):
                outer.requests.append(("GET", self.path, dict(self.headers), b""))
                self._reply(200, {"id": "u1", "status": "done"})

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


def write_report(tmp_path: Path, name="report.xml") -> Path:
    path = tmp_path / name
    path.write_bytes(REPORT)
    return path


def test_github_actions_metadata_is_detected():
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_SHA": "abc123",
        "GITHUB_REF_NAME": "main",
        "GITHUB_RUN_ID": "42",
        "GITHUB_RUN_ATTEMPT": "2",
    }
    meta = detect_ci_metadata(env)
    assert meta.commit_sha == "abc123"
    assert (meta.branch, meta.ci_run_id, meta.attempt) == ("main", "42", 2)


def test_pull_request_uses_head_branch():
    env = {"GITHUB_ACTIONS": "true", "GITHUB_HEAD_REF": "feat/x", "GITHUB_REF_NAME": "7/merge"}
    assert detect_ci_metadata(env).branch == "feat/x"


def test_no_ci_means_no_metadata():
    meta = detect_ci_metadata({})
    assert (meta.commit_sha, meta.branch, meta.ci_run_id, meta.attempt) == (None, None, None, 1)


def test_multipart_contains_fields_and_file():
    body, content_type = encode_multipart({"branch": "main"}, "file", "dir/r.xml", REPORT)
    boundary = content_type.split("boundary=")[1]
    assert body.startswith(f"--{boundary}".encode())
    assert b'name="branch"\r\n\r\nmain' in body
    assert b'filename="r.xml"' in body
    assert REPORT in body
    assert body.endswith(f"--{boundary}--\r\n".encode())


def test_globs_are_expanded_and_deduplicated(tmp_path):
    write_report(tmp_path, "a.xml")
    write_report(tmp_path, "b.xml")
    paths = expand_paths([str(tmp_path / "*.xml"), str(tmp_path / "a.xml")])
    assert [Path(p).name for p in paths] == ["a.xml", "b.xml"]


def test_upload_sends_token_and_metadata(tmp_path):
    server = FakeServer()
    try:
        report = write_report(tmp_path)
        code = main(
            [str(report), "--server", server.url, "--project", "demo", "--token", "fr_x",
             "--commit", "abc", "--branch", "main", "--wait"],
            env={},
        )
    finally:
        server.close()

    assert code == 0
    method, path, headers, body = server.requests[0]
    assert (method, path) == ("POST", "/api/v1/projects/demo/uploads")
    assert headers["Authorization"] == "Bearer fr_x"
    assert b'name="commit_sha"\r\n\r\nabc' in body
    assert server.requests[1][:2] == ("GET", "/api/v1/uploads/u1")


def test_server_error_warns_but_exits_zero_by_default(tmp_path, capsys):
    server = FakeServer(upload_status=401, upload_body={"detail": "The API token is invalid"})
    try:
        report = write_report(tmp_path)
        args = [str(report), "--server", server.url, "--project", "demo", "--token", "bad"]
        assert main(args, env={}) == 0
        assert main([*args, "--fail-on-error"], env={}) == 1
    finally:
        server.close()
    assert "The API token is invalid" in capsys.readouterr().err


def test_missing_settings_is_a_usage_error(tmp_path):
    assert main([str(write_report(tmp_path))], env={}) == 2


def test_unreachable_server_with_fail_on_error(tmp_path):
    report = write_report(tmp_path)
    args = [str(report), "--server", "http://127.0.0.1:9", "--project", "p", "--token", "t",
            "--fail-on-error"]
    assert main(args, env={}) == 1
