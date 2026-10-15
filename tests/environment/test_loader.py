"""Tests for `load_environment` on a tiny fake environment written to a temporary directory."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from mcp_ipi.environment import YamlLoadError, load_environment


class FakeEmail(BaseModel):
    subject: str
    body: str
    sent: datetime


class FakeInbox(BaseModel):
    owner: str
    emails: list[FakeEmail]


class FakeWeb(BaseModel):
    pages: dict[str, str]


class FakeEnvironment(BaseModel):
    inbox: FakeInbox
    web: FakeWeb


class FakeWebOnlyEnvironment(BaseModel):
    web: FakeWeb


def write_yaml(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_environment(tmp_path: Path, body: str = "Invoice attached.", content: str = "News") -> Path:
    write_yaml(
        tmp_path / "components" / "inbox.yaml",
        f'owner: alice\nemails:\n  - subject: Invoice\n    body: "{body}"\n    sent: 2026-09-30T14:05:00Z\n',
    )
    write_yaml(tmp_path / "components" / "web.yaml", f'pages:\n  www.news.com: "{content}"\n')
    return write_yaml(
        tmp_path / "environment.yaml", "inbox: !include components/inbox.yaml\nweb: !include components/web.yaml\n"
    )


def test_environment_with_included_components_loads_into_the_given_class(tmp_path: Path):
    path = write_environment(tmp_path)

    env = load_environment(path, FakeEnvironment)

    assert isinstance(env, FakeEnvironment)
    assert env == FakeEnvironment(
        inbox=FakeInbox(
            owner="alice",
            emails=[
                FakeEmail(subject="Invoice", body="Invoice attached.", sent=datetime(2026, 9, 30, 14, 5, tzinfo=UTC))
            ],
        ),
        web=FakeWeb(pages={"www.news.com": "News"}),
    )


def test_placeholder_in_an_included_file_is_filled(tmp_path: Path):
    path = write_environment(tmp_path, body="Invoice attached. {@inject:email_body}")

    env = load_environment(path, FakeEnvironment, {"email_body": "Thanks!"})

    assert env.inbox.emails[0].body == "Invoice attached. Thanks!"


def test_same_placeholder_twice_and_different_placeholders_are_all_filled(tmp_path: Path):
    path = write_environment(
        tmp_path, body="{@inject:email_body} {@inject:email_body}", content="News {@inject:web_page}"
    )

    env = load_environment(path, FakeEnvironment, {"email_body": "A", "web_page": "B"})

    assert env.inbox.emails[0].body == "A A"
    assert env.web.pages == {"www.news.com": "News B"}


@pytest.mark.parametrize("injections", [None, {"other": "X"}], ids=["left-out", "missing-id"])
def test_placeholder_without_text_raises_key_error_naming_the_id(tmp_path: Path, injections: dict[str, str] | None):
    path = write_environment(tmp_path, body="{@inject:email_body}")

    with pytest.raises(KeyError, match="email_body"):
        load_environment(path, FakeEnvironment, injections)


def test_data_without_placeholders_loads_without_injections(tmp_path: Path):
    path = write_yaml(tmp_path / "environment.yaml", "web:\n  pages:\n    www.a.com: Hello\n")

    assert load_environment(path, FakeWebOnlyEnvironment) == FakeWebOnlyEnvironment(
        web=FakeWeb(pages={"www.a.com": "Hello"})
    )


def test_injection_whose_id_is_not_in_the_data_is_ignored(tmp_path: Path):
    path = write_environment(tmp_path)

    env = load_environment(path, FakeEnvironment, {"unused": "X"})

    assert env.inbox.emails[0].body == "Invoice attached."


@pytest.mark.parametrize(
    "text",
    ["web: {}\n", "web:\n  pages: [not, a, dict]\n"],
    ids=["missing-field", "wrong-type"],
)
def test_invalid_data_raises_validation_error(tmp_path: Path, text: str):
    path = write_yaml(tmp_path / "environment.yaml", text)

    with pytest.raises(ValidationError):
        load_environment(path, FakeWebOnlyEnvironment)


def test_missing_environment_file_raises_yaml_load_error(tmp_path: Path):
    with pytest.raises(YamlLoadError):
        load_environment(tmp_path / "missing.yaml", FakeEnvironment)


def test_two_calls_return_equal_but_independent_objects(tmp_path: Path):
    path = write_environment(tmp_path)

    first = load_environment(path, FakeEnvironment)
    second = load_environment(path, FakeEnvironment)
    assert first == second

    first.inbox.emails.append(first.inbox.emails[0])

    assert len(second.inbox.emails) == 1
