#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"
CONTRACT = json.loads((ROOT / "canonical-quote-v1-source.json").read_text(encoding="utf-8"))


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def git_blob(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


interfaces = SOURCES / "interfaces"
api = SOURCES / "api"
web = SOURCES / "web"

for key, path in (("canonicalInterfaces", interfaces), ("canonicalApi", api), ("canonicalWeb", web)):
    expected = CONTRACT[key]["commit"]
    observed = git_head(path)
    if observed != expected:
        raise SystemExit(f"{key} exact-head mismatch")

fixture_directory = Path(CONTRACT["fixtureDirectory"])
interface_fixtures = interfaces / fixture_directory
api_fixtures = api / fixture_directory
web_fixtures = web / fixture_directory

for name, expected_blob in CONTRACT["fixtureGitBlobs"].items():
    authoritative = interface_fixtures / name
    if git_blob(authoritative) != expected_blob:
        raise SystemExit(f"authoritative fixture blob mismatch: {name}")
    for consumer_name, consumer_root in (("api", api_fixtures), ("web", web_fixtures)):
        candidate = consumer_root / name
        if not candidate.is_file() or candidate.read_bytes() != authoritative.read_bytes():
            raise SystemExit(f"{consumer_name} fixture drift: {name}")

manifest = load_json(interface_fixtures / "manifest.json")
if manifest.get("schemaVersion") != 1 or manifest.get("wireCase") != "camelCase":
    raise SystemExit("quote fixture manifest drift")

request = load_json(interface_fixtures / "request.json")
expected_fields = {
    "organizationName",
    "contactName",
    "contactEmail",
    "website",
    "employeeCount",
    "annualRevenueBand",
    "frameworks",
    "currentStage",
    "infrastructure",
    "dataSensitivity",
    "targetDate",
    "hasSecurityProgram",
    "hasPolicies",
    "hasRiskAssessment",
    "hasIncidentResponsePlan",
    "hasVendorManagement",
    "notes",
    "contextKey",
    "answersVersion",
}
if set(request) != expected_fields:
    raise SystemExit("canonical request field set drift")
if request["answersVersion"] != 1 or request["contextKey"] != "quote-analysis":
    raise SystemExit("canonical request version or context-key drift")
if "nist_800_53" not in request["frameworks"]:
    raise SystemExit("NIST 800-53 canonical spelling drift")
for forbidden in (
    "userId",
    "user_id",
    "tenantId",
    "tenant_id",
    "contextRecordId",
    "context_record_id",
    "markdownContext",
    "markdown_context",
    "company_name",
    "target_frameworks",
):
    if forbidden in request:
        raise SystemExit(f"forbidden caller-controlled field: {forbidden}")

api_lock = load_json(api / "interfaces.lock.json")
api_interface = api_lock["canonical_interfaces"]
if api_interface["commit"] != CONTRACT["canonicalInterfaces"]["commit"]:
    raise SystemExit("API interface commit drift")
if api_interface["quote_request_fixture"]["git_blob"] != CONTRACT["fixtureGitBlobs"]["request.json"]:
    raise SystemExit("API request fixture pin drift")

web_lock = load_json(web_fixtures / "UPSTREAM.lock.json")
if web_lock["fixtureCommit"] != CONTRACT["canonicalInterfaces"]["goldenFixtureCommit"]:
    raise SystemExit("web golden fixture commit drift")
for name, expected_blob in CONTRACT["fixtureGitBlobs"].items():
    if web_lock["files"].get(name) != expected_blob:
        raise SystemExit(f"web fixture provenance drift: {name}")

api_lib = (api / "src/lib.rs").read_text(encoding="utf-8")
api_contract = (api / "src/contract.rs").read_text(encoding="utf-8")
if '"/api/v1/quotes"' not in api_lib or '"/api/v1/quotes/{quote_id}/events"' not in api_lib:
    raise SystemExit("canonical API route drift")
if 'rename_all = "camelCase"' not in api_contract or "deny_unknown_fields" not in api_contract:
    raise SystemExit("API canonical parser is not fail-closed")
if "context_record_id" in api_contract or "markdown_context" in api_contract:
    raise SystemExit("API public contract exposes server-owned context")
if 'DEFAULT_GEMINI_MODEL: &str = "gemini-3.6-flash"' not in api_lib:
    raise SystemExit("API reviewed model drift")

web_client = (web / "src/quote_api.rs").read_text(encoding="utf-8")
web_route = (web / "src/routes/quote.rs").read_text(encoding="utf-8")
if '.post(format!("{}/api/v1/quotes", self.base_url))' not in web_client:
    raise SystemExit("web create route drift")
if 'rename_all = "camelCase"' not in web_client or "deny_unknown_fields" not in web_client:
    raise SystemExit("web canonical request parser drift")
for required in (
    "actor.email",
    "QuoteRequest::fixed_context_key()",
    'name="nist_800_53"',
    'name="has_vendor_management"',
    'require_origin(&headers, &state)',
    'require_csrf(&actor, &headers, Some(&form.csrf))',
):
    if required not in web_route:
        raise SystemExit(f"web quote security/contract boundary missing: {required}")
for forbidden in (
    'name="context_record_id"',
    'name="contextRecordId"',
    'name="markdown_context"',
    'name="user_id"',
    'name="tenant_id"',
):
    if forbidden in web_route:
        raise SystemExit(f"web form exposes server-owned field: {forbidden}")

credential = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{20,}|lin_api_[A-Za-z0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY"
)
for path in (ROOT / "canonical-quote-v1-source.json", ROOT / "scripts/verify_canonical_quote_v1.py"):
    if credential.search(path.read_text(encoding="utf-8")):
        raise SystemExit(f"credential-shaped content: {path.relative_to(ROOT)}")

print(
    "certified canonical quote v1 contract: "
    f"interfaces={CONTRACT['canonicalInterfaces']['commit']} "
    f"api={CONTRACT['canonicalApi']['commit']} "
    f"web={CONTRACT['canonicalWeb']['commit']}"
)
