"""Tests for `load_yaml` on small YAML files written to a temporary directory."""

import re
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml
from yaml.composer import ComposerError
from yaml.constructor import ConstructorError

from mcp_ipi.environment import YamlLoadError, load_yaml

# Modules that importing `mcp_ipi.environment` must not load (checked in a fresh interpreter).
# The environment layer is generic: it knows nothing about domains, suites, the MCP SDK or anything above it.
FORBIDDEN_IMPORTS = [
    "mcp_ipi.domains",
    "mcp_ipi.suites",
    "mcp_ipi.mcp",
    "mcp_ipi.agent",
    "mcp_ipi.attacks",
    "mcp_ipi.defenses",
    "mcp_ipi.runner",
    "mcp",
]


def write_yaml(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_mapping_document_loads_as_dict(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "name: Alice\nage: 30\nactive: true\n")

    assert load_yaml(path) == {"name": "Alice", "age": 30, "active": True}


def test_list_document_loads_as_list(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "- one\n- 2\n- null\n")

    assert load_yaml(path) == ["one", 2, None]


def test_scalar_document_loads_as_scalar(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "just a string\n")

    assert load_yaml(path) == "just a string"


def test_empty_file_loads_as_none(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "")

    assert load_yaml(path) is None


def test_non_ascii_utf8_text_round_trips(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "subject: Čestitke — naročilo €5 ✓\n")

    assert load_yaml(path) == {"subject": "Čestitke — naročilo €5 ✓"}


def test_dates_and_datetimes_load_as_date_and_datetime(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "day: 2026-09-30\nsent: 2026-09-30T14:05:00Z\n")

    assert load_yaml(path) == {"day": date(2026, 9, 30), "sent": datetime(2026, 9, 30, 14, 5, tzinfo=UTC)}


def test_anchors_aliases_and_merge_keys_work(tmp_path: Path):
    path = write_yaml(
        tmp_path / "data.yaml",
        "base: &base\n  sender: alice@corp.com\n  read: false\ncopy: *base\nmerged:\n  <<: *base\n  read: true\n",
    )

    assert load_yaml(path) == {
        "base": {"sender": "alice@corp.com", "read": False},
        "copy": {"sender": "alice@corp.com", "read": False},
        "merged": {"sender": "alice@corp.com", "read": True},
    }


def test_quoted_inject_placeholder_is_returned_unchanged(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", 'body: "Invoice attached. {@inject:email_body}"\n')

    assert load_yaml(path) == {"body": "Invoice attached. {@inject:email_body}"}


def test_yaml_load_error_is_a_value_error():
    assert issubclass(YamlLoadError, ValueError)


def test_missing_file_raises_yaml_load_error_naming_the_path(tmp_path: Path):
    path = tmp_path / "missing.yaml"

    with pytest.raises(YamlLoadError, match=re.escape(str(path))):
        load_yaml(path)


@pytest.mark.parametrize(
    "text",
    ["payload: !!python/object:builtins.object {}\n", "home: !env HOME\n"],
    ids=["python-tag", "unknown-local-tag"],
)
def test_unsafe_or_unknown_tag_is_rejected(tmp_path: Path, text: str):
    path = write_yaml(tmp_path / "data.yaml", text)

    with pytest.raises(ConstructorError, match=re.escape(str(path))):
        load_yaml(path)


def test_file_with_two_documents_is_rejected(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "a: 1\n---\nb: 2\n")

    with pytest.raises(ComposerError, match=re.escape(str(path))):
        load_yaml(path)


def test_syntax_error_names_the_file_and_line(tmp_path: Path):
    path = write_yaml(tmp_path / "data.yaml", "a: 1\nb: [unclosed\n")

    with pytest.raises(yaml.YAMLError, match=re.escape(str(path))) as error:
        load_yaml(path)

    assert "line 3" in str(error.value)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("inbox: !include part.yaml\n", {"inbox": {"owner": "alice"}}),
        ("- first\n- !include part.yaml\n", ["first", {"owner": "alice"}]),
        ("!include part.yaml\n", {"owner": "alice"}),
    ],
    ids=["mapping-value", "list-item", "whole-document"],
)
def test_include_is_replaced_by_the_included_content(tmp_path: Path, text: str, expected: object):
    write_yaml(tmp_path / "part.yaml", "owner: alice\n")
    path = write_yaml(tmp_path / "data.yaml", text)

    assert load_yaml(path) == expected


@pytest.mark.parametrize(
    ("part", "expected"),
    [("a: 1\nb: [x, y]\n", {"a": 1, "b": ["x", "y"]}), ("- 1\n- two\n", [1, "two"]), ("42\n", 42)],
    ids=["mapping", "list", "scalar"],
)
def test_included_file_can_hold_any_shape(tmp_path: Path, part: str, expected: object):
    write_yaml(tmp_path / "part.yaml", part)
    path = write_yaml(tmp_path / "data.yaml", "value: !include part.yaml\n")

    assert load_yaml(path) == {"value": expected}


def test_nested_includes_resolve_relative_to_each_including_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    write_yaml(tmp_path / "data" / "components" / "parts" / "emails.yaml", "- id: '1'\n  subject: Hi\n")
    write_yaml(tmp_path / "data" / "components" / "inbox.yaml", "owner: alice\nemails: !include parts/emails.yaml\n")
    path = write_yaml(tmp_path / "data" / "environment.yaml", "inbox: !include components/inbox.yaml\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert load_yaml(path) == {"inbox": {"owner": "alice", "emails": [{"id": "1", "subject": "Hi"}]}}


def test_same_file_included_twice_loads_as_independent_objects(tmp_path: Path):
    write_yaml(tmp_path / "part.yaml", "tags: [a]\n")
    path = write_yaml(tmp_path / "data.yaml", "first: !include part.yaml\nsecond: !include part.yaml\n")

    data = load_yaml(path)
    data["first"]["tags"].append("b")

    assert data["second"] == {"tags": ["a"]}


def test_loading_does_not_change_the_global_safe_loader(tmp_path: Path):
    write_yaml(tmp_path / "a.yaml", "a: 1\n")
    load_yaml(write_yaml(tmp_path / "data.yaml", "a: !include a.yaml\n"))

    with pytest.raises(ConstructorError):
        yaml.safe_load("x: !include a.yaml")


def test_importing_environment_does_not_load_domains_or_higher_layers():
    code = f"import sys, mcp_ipi.environment; print(*(m for m in {FORBIDDEN_IMPORTS!r} if m in sys.modules))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

    assert result.stdout.split() == []
