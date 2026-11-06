from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.ingest.junit import (
    MAX_MESSAGE_CHARS,
    JUnitParseError,
    identity_hash_for,
    parse_junit_xml,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "junit"


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def by_name(report, name):
    return next(case for case in report.test_cases if case.name == name)


def test_pytest_report_statuses_and_counts():
    report = parse_junit_xml(load("pytest.xml"))

    assert len(report.test_cases) == 5
    assert report.count("passed") == 2
    assert report.count("failed") == 1
    assert report.count("error") == 1
    assert report.count("skipped") == 1
    assert report.timestamp == datetime(2026, 11, 5, 14, 2, 11, 418392, tzinfo=UTC)


def test_pytest_failure_details():
    report = parse_junit_xml(load("pytest.xml"))
    case = by_name(report, "test_payment_timeout")

    assert case.classname == "tests.test_checkout"
    assert case.suite == "pytest"
    assert case.duration_ms == 1502
    assert case.failure_message is not None
    assert case.failure_message.startswith("AssertionError: expected status 200, got 504")
    assert by_name(report, "test_bulk_import").failure_message is None  # skips carry no message


def test_jest_report_with_naive_timestamp_is_utc():
    report = parse_junit_xml(load("jest.xml"))

    assert report.count("failed") == 1
    assert report.timestamp == datetime(2026, 11, 5, 14, 5, tzinfo=UTC)
    failed = by_name(report, "CartSummary updates when an item is removed")
    assert "Timed out in waitFor" in (failed.failure_message or "")


def test_surefire_flaky_failure_marks_retried_but_passed():
    report = parse_junit_xml(load("junit5_surefire.xml"))
    case = by_name(report, "publishesEventOnce()")

    assert case.status == "passed"
    assert case.retried is True
    assert by_name(report, "createsOrder()").retried is False
    assert report.timestamp is None


def test_nested_suites_and_odd_durations():
    report = parse_junit_xml(load("nested_suites.xml"))

    assert [case.name for case in report.test_cases] == [
        "test_create_user",
        "test_delete_user",
        "test_list_orders",
    ]
    assert by_name(report, "test_create_user").file == "tests/api/users.py"
    assert by_name(report, "test_delete_user").duration_ms == 1_234_500  # "1,234.5" seconds
    assert by_name(report, "test_list_orders").duration_ms == 0  # unparseable time


def test_identity_ignores_suite_name():
    assert identity_hash_for("tests.test_a", "test_x") == identity_hash_for(
        "tests.test_a", "test_x"
    )
    assert identity_hash_for("tests.test_a", "test_x") != identity_hash_for(
        "tests.test_b", "test_x"
    )
    report = parse_junit_xml(load("pytest.xml"))
    case = by_name(report, "test_total_includes_tax")
    assert case.identity_hash == identity_hash_for("tests.test_checkout", "test_total_includes_tax")


def test_long_failure_message_is_truncated():
    message = "x" * (MAX_MESSAGE_CHARS * 2)
    xml = (
        '<testsuite name="s"><testcase classname="c" name="t">'
        f'<failure message="{message}"/></testcase></testsuite>'
    ).encode()
    case = parse_junit_xml(xml).test_cases[0]

    assert case.failure_message is not None
    assert len(case.failure_message) == MAX_MESSAGE_CHARS


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("malformed.xml", "not valid XML"),
        ("xxe.xml", "unsafe XML"),
        ("not_junit.xml", "found <html>"),
        ("empty_suite.xml", "no <testcase>"),
    ],
)
def test_bad_reports_are_rejected_with_a_reason(fixture, expected):
    with pytest.raises(JUnitParseError, match=expected):
        parse_junit_xml(load(fixture))


def test_empty_file_is_rejected():
    with pytest.raises(JUnitParseError, match="empty"):
        parse_junit_xml(b"   ")


def test_testcase_without_name_is_rejected():
    with pytest.raises(JUnitParseError, match="missing its name"):
        parse_junit_xml(b'<testsuite name="s"><testcase classname="c"/></testsuite>')
