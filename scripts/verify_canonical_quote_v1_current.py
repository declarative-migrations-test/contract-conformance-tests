#!/usr/bin/env python3
"""Fail-closed cross-repository certification for Canonical quote API v1."""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
MATRIX = ROOT / "contracts" / "canonical-quote-v1-current.json"


def fail(message: str) -> None:
    raise SystemExit(f"canonical quote v1 conformance failed: {message}")


def read_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path}: {exc}")


def git_head(path: pathlib.Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def source_text(root: pathlib.Path) -> str:
    pieces: list[str] = []
    for suffix in ("*.rs", "*.toml", "*.json", "*.md", "*.py", "*.sh"):
        for path in sorted(root.rglob(suffix)):
            if any(part in {".git", "target", "node_modules", ".dart_tool"} for part in path.parts):
                continue
            try:
                pieces.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                continue
    return "\n".join(pieces)


def assert_exact_head(name: str, root: pathlib.Path, expected: str) -> None:
    actual = git_head(root)
    if actual != expected:
        fail(f"{name} head {actual} does not equal pinned {expected}")


def assert_fixture_contract(interfaces: pathlib.Path, paths: list[str]) -> dict[str, Any]:
    fixtures: dict[str, Any] = {}
    for relative in paths:
        path = interfaces / relative
        if not path.is_file():
            fail(f"authoritative fixture is missing: {relative}")
        fixtures[path.name] = read_json(path)

    request = fixtures["create-request.json"]
    required_request = {
        "organizationName",
        "contactName",
        "contactEmail",
        "employeeCount",
        "frameworks",
        "currentStage",
        "infrastructure",
        "dataSensitivity",
        "hasSecurityProgram",
        "hasPolicies",
        "hasRiskAssessment",
        "hasIncidentResponsePlan",
        "hasVendorManagement",
        "answersVersion",
    }
    missing = sorted(required_request - request.keys())
    if missing:
        fail(f"authoritative request misses {missing}")
    forbidden = {
        "company",
        "company_name",
        "companyName",
        "target_frameworks",
        "cloud_providers",
        "handles_phi",
        "employee_count",
        "user_id",
        "tenant_id",
        "markdown_context",
        "context_record_id",
    }
    present = sorted(forbidden & request.keys())
    if present:
        fail(f"authoritative request contains legacy or identity fields {present}")
    expected_frameworks = {
        "soc2_type_1",
        "soc2_type_2",
        "nist_csf_2",
        "nist_800_53",
        "hipaa",
        "iso_27001",
        "pci_dss_4",
        "fedramp",
        "gdpr",
    }
    if not expected_frameworks.issubset(set(request["frameworks"])):
        fail("authoritative request does not exercise the complete framework matrix")

    submission = fixtures["submission-response.json"]
    if set(submission) != {"quoteId", "status", "streamUrl", "createdAt"}:
        fail("submission response field set drifted")

    detail = fixtures["detail-ready.json"]
    if detail.get("quoteId") != submission.get("quoteId"):
        fail("detail and submission quote IDs diverge")
    if detail.get("status") != "ready" or "estimate" not in detail:
        fail("ready detail must contain a ready status and estimate")

    listing = fixtures["list-response.json"]
    if not isinstance(listing.get("quotes"), list) or "nextCursor" not in listing:
        fail("list response must expose quotes plus nextCursor")

    event = fixtures["status-event.json"]
    for field in ("quoteId", "sequence", "stage", "message", "terminal", "occurredAt"):
        if field not in event:
            fail(f"status event misses {field}")

    problem = fixtures["problem.json"]
    if set(problem) != {"code", "message", "requestId"}:
        fail("public problem field set drifted")
    return fixtures


def assert_fixture_copy(
    consumer_name: str,
    consumer: pathlib.Path,
    interfaces: pathlib.Path,
    relative: str,
) -> None:
    authoritative = interfaces / relative
    candidate = consumer / relative
    if not candidate.is_file():
        fail(f"{consumer_name} does not carry {relative}")
    a = authoritative.read_bytes()
    b = candidate.read_bytes()
    if a != b:
        fail(
            f"{consumer_name} fixture {relative} differs: "
            f"{hashlib.sha256(b).hexdigest()} != {hashlib.sha256(a).hexdigest()}"
        )


def require_tokens(name: str, text: str, tokens: tuple[str, ...]) -> None:
    for token in tokens:
        if token not in text:
            fail(f"{name} source does not contain required contract token {token!r}")


def assert_api_contract(api: pathlib.Path, interfaces: pathlib.Path) -> None:
    assert_fixture_copy("api", api, interfaces, "fixtures/quote-v1/create-request.json")
    text = source_text(api)
    require_tokens(
        "api",
        text,
        (
            "/api/v1/quotes",
            "Idempotency-Key",
            "QuoteSubmissionResponse",
            "QuoteDetail",
            "QuoteListResponse",
            "QuoteRetryResponse",
            "QuoteStatusEvent",
            "occurred_at",
            "canonical_quote_operation",
            "FORCE ROW LEVEL SECURITY",
            "canonical_cloud__quote",
        ),
    )
    for legacy in (
        '"completed".into()',
        "pub organization: OrganizationInput",
        "pub markdown_context: String",
    ):
        if legacy in text:
            fail(f"api still exposes legacy public contract fragment {legacy!r}")
    schema = (api / "db" / "schema.sql").read_text(encoding="utf-8")
    for token in (
        "CREATE TABLE IF NOT EXISTS canonical_cloud__quote.canonical_quote_operation",
        "ENABLE ROW LEVEL SECURITY",
        "FORCE ROW LEVEL SECURITY",
        "owner_subject",
        "idempotency_key",
    ):
        if token not in schema:
            fail(f"api schema misses {token!r}")


def assert_web_contract(web: pathlib.Path, interfaces: pathlib.Path) -> None:
    assert_fixture_copy("web", web, interfaces, "fixtures/quote-v1/create-request.json")
    text = source_text(web)
    require_tokens(
        "web",
        text,
        (
            "/u/quote",
            "/api/v1/quotes",
            "QuoteSubmissionResponse",
            "QuoteDetail",
            "QuoteListResponse",
            "QuoteStatusEvent",
            "Idempotency-Key",
            "CANONICAL_INTERNAL_AUTH_TOKEN",
        ),
    )
    if "GEMINI_API_KEY" in text or "DATABASE_URL" in text:
        fail("web source must not own Gemini or quote-database credentials")
    for legacy in ("ApiQuoteRecord", "company_name", "target_frameworks"):
        if legacy in text:
            fail(f"web still exposes legacy quote transport {legacy!r}")


def assert_dependency_pins(api: pathlib.Path, web: pathlib.Path, matrix: dict[str, Any]) -> None:
    expected_interfaces = matrix["interfaces"]["commit"]
    expected_lib = matrix["canonical_lib"]["commit"]
    combined = source_text(api) + "\n" + source_text(web)
    if expected_interfaces not in combined:
        fail("consumer source does not pin the authoritative interface revision")
    if expected_lib not in source_text(api):
        fail("api does not pin the reviewed canonical-lib revision")


def main() -> None:
    matrix = read_json(MATRIX)
    if matrix.get("schema_version") != 1:
        fail("matrix schema version must be 1")
    if len(sys.argv) != 4:
        fail("usage: verify_canonical_quote_v1_current.py INTERFACES API WEB")
    interfaces, api, web = map(pathlib.Path, sys.argv[1:])
    assert_exact_head("interfaces", interfaces, matrix["interfaces"]["commit"])
    assert_exact_head("api", api, matrix["api"]["commit"])
    assert_exact_head("web", web, matrix["web"]["commit"])
    assert_fixture_contract(interfaces, matrix["required_fixture_paths"])
    assert_api_contract(api, interfaces)
    assert_web_contract(web, interfaces)
    assert_dependency_pins(api, web, matrix)
    print("canonical quote v1 current-head conformance passed")


if __name__ == "__main__":
    main()
