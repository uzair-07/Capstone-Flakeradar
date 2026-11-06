"""Parse JUnit XML reports into a framework-neutral structure.

Handles the dialects written by pytest (``--junitxml``), jest-junit, and Maven Surefire /
JUnit 5, including nested ``<testsuite>`` elements. XML is parsed with defusedxml so
entity-expansion and external-entity attacks are rejected.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from xml.etree.ElementTree import Element, ParseError

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

MAX_TESTCASES = 100_000
MAX_MESSAGE_CHARS = 4_000

# Elements that record an earlier failed attempt of a test that was re-run.
RETRY_TAGS = ("rerunFailure", "rerunError", "flakyFailure", "flakyError")


class JUnitParseError(ValueError):
    """The file is not a usable JUnit XML report. Retrying will not help."""


@dataclass(frozen=True)
class ParsedTestCase:
    suite: str
    classname: str
    name: str
    file: str | None
    status: str  # passed | failed | error | skipped
    duration_ms: int
    retried: bool
    failure_message: str | None

    @property
    def identity_hash(self) -> str:
        return identity_hash_for(self.classname, self.name)


@dataclass(frozen=True)
class ParsedReport:
    test_cases: list[ParsedTestCase]
    timestamp: datetime | None

    def count(self, status: str) -> int:
        return sum(1 for case in self.test_cases if case.status == status)

    @property
    def duration_ms(self) -> int:
        return sum(case.duration_ms for case in self.test_cases)


def identity_hash_for(classname: str, name: str) -> str:
    """Stable identity of a test within a project.

    The suite name is left out on purpose: pytest names every suite "pytest", and some
    reporters vary it between runs, while classname + name stay stable.
    """
    return hashlib.sha256(f"{classname}\x1f{name}".encode()).hexdigest()



def parse_junit_xml(data: bytes) -> ParsedReport:
    if not data.strip():
        raise JUnitParseError("The file is empty.")
    try:
        root = SafeET.fromstring(data, forbid_dtd=True)
    except DefusedXmlException as exc:
        raise JUnitParseError(
            f"Rejected unsafe XML ({exc.__class__.__name__}). JUnit reports never need a DTD "
            "or entities."
        ) from exc
    except ParseError as exc:
        raise JUnitParseError(f"The file is not valid XML: {exc}") from exc

    if root.tag not in ("testsuites", "testsuite"):
        raise JUnitParseError(
            f"Expected a <testsuites> or <testsuite> root element, found <{root.tag}>."
        )

    cases: list[ParsedTestCase] = []
    timestamp = _parse_timestamp(root.get("timestamp"))
    for suite in root.iter("testsuite"):
        timestamp = timestamp or _parse_timestamp(suite.get("timestamp"))
        suite_name = (suite.get("name") or "").strip()
        for element in suite.findall("testcase"):
            cases.append(_parse_case(element, suite_name, suite.get("file")))
            if len(cases) > MAX_TESTCASES:
                raise JUnitParseError(
                    f"The report has more than {MAX_TESTCASES:,} test cases; split it into "
                    "several files."
                )

    if not cases:
        raise JUnitParseError("The report contains no <testcase> elements.")
    return ParsedReport(test_cases=cases, timestamp=timestamp)


def _parse_case(element: Element, suite_name: str, suite_file: str | None) -> ParsedTestCase:
    name = (element.get("name") or "").strip()
    if not name:
        raise JUnitParseError("A <testcase> element is missing its name attribute.")
    classname = (element.get("classname") or "").strip()

    status, message = "passed", None
    for tag, mapped in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
        child = element.find(tag)
        if child is not None:
            status, message = mapped, _message(child)
            break

    retried = any(element.find(tag) is not None for tag in RETRY_TAGS)

    return ParsedTestCase(
        suite=suite_name,
        classname=classname,
        name=name,
        file=(element.get("file") or suite_file or None),
        status=status,
        duration_ms=_parse_duration_ms(element.get("time")),
        retried=retried,
        failure_message=message if status in ("failed", "error") else None,
    )


def _message(element: Element) -> str | None:
    parts = [element.get("message") or "", (element.text or "").strip()]
    text = "\n".join(part for part in parts if part).strip()
    if not text:
        return None
    if len(text) > MAX_MESSAGE_CHARS:
        text = text[: MAX_MESSAGE_CHARS - 1] + "…"
    return text


def _parse_duration_ms(value: str | None) -> int:
    if not value:
        return 0
    try:
        seconds = float(value.replace(",", ""))
    except ValueError:
        return 0
    if seconds != seconds or seconds < 0:  # NaN or negative
        return 0
    return round(seconds * 1000)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
