"""Tests for the cloud storage tools on hand-built drives."""

from datetime import UTC, datetime

import pytest

from mcp_ipi.domains.cloud_storage import CloudDrive, File, FileInfo
from mcp_ipi.domains.cloud_storage.tools import (
    append_to_file,
    create_file,
    delete_file,
    get_file_by_id,
    list_files,
    search_files,
    share_file,
)


def make_drive() -> CloudDrive:
    return CloudDrive(
        account_email="me@corp.com",
        current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        files=[
            File(
                id="0",
                filename="budget-2026.xlsx",
                content="Marketing: 12000 EUR\nTravel: 4000 EUR",
                owner="me@corp.com",
                shared_with={"alice@corp.com": "rw"},
                last_modified=datetime(2026, 5, 10, 14, 0, tzinfo=UTC),
            ),
            File(
                id="1",
                filename="meeting-notes.txt",
                content="Discussed the Q2 budget and the offsite.",
                owner="alice@corp.com",
                shared_with={"me@corp.com": "r"},
                last_modified=datetime(2026, 5, 12, 11, 0, tzinfo=UTC),
            ),
        ],
    )


def info(file: File) -> FileInfo:
    return FileInfo(
        id=file.id,
        filename=file.filename,
        owner=file.owner,
        shared_with=file.shared_with,
        last_modified=file.last_modified,
    )


def test_list_files_returns_every_file_without_its_content_and_without_changing_drive():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    files = list_files(drive)

    assert files == [info(file) for file in before.files]
    assert drive == before


def test_list_files_returns_a_copy_of_the_file_list():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    list_files(drive).clear()

    assert drive == before


def make_search_drive(*files: tuple[str, str]) -> CloudDrive:
    return CloudDrive(
        account_email="me@corp.com",
        current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        files=[
            File(
                id=str(index),
                filename=filename,
                content=content,
                owner="me@corp.com",
                last_modified=datetime(2026, 5, 10, 14, 0, tzinfo=UTC),
            )
            for index, (filename, content) in enumerate(files)
        ],
    )


def search_ids(drive: CloudDrive, query: str) -> list[str]:
    return [file.id for file in search_files(drive, query)]


def test_search_files_returns_matching_files_without_their_content_and_without_changing_drive():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    assert search_files(drive, "BUDGET") == [info(file) for file in before.files]
    assert search_files(drive, "offsite") == [info(before.files[1])]
    assert drive == before


def test_search_files_matches_a_word_only_in_the_content():
    assert search_ids(make_drive(), "marketing") == ["0"]


def test_search_files_ranks_files_with_more_query_words_first():
    drive = make_search_drive(
        ("notes.txt", "The budget."),
        ("plan.txt", "The offsite budget for travel."),
        ("trip.txt", "Offsite travel."),
    )

    assert search_ids(drive, "offsite budget travel") == ["1", "2", "0"]


def test_search_files_keeps_drive_order_for_equal_scores():
    drive = make_search_drive(("b.txt", "Budget."), ("a.txt", "Travel."), ("c.txt", "Budget and travel."))

    assert search_ids(drive, "travel budget") == ["2", "0", "1"]


def test_search_files_matches_words_split_across_filename_and_content():
    assert search_ids(make_drive(), "2026 travel") == ["0"]


def test_search_files_leaves_out_files_that_match_no_word():
    assert search_ids(make_drive(), "offsite invoice") == ["1"]


def test_search_files_returns_empty_list_when_no_word_matches():
    assert search_files(make_drive(), "invoice receipt") == []


def test_search_files_matches_whole_words_case_insensitively():
    drive = make_search_drive(("policy.txt", "Written by HR."), ("count.txt", "Three items."))

    assert search_ids(drive, "hr") == ["0"]
    assert search_ids(drive, "THREE") == ["1"]
    assert search_ids(drive, "polic") == []


def test_search_files_counts_a_repeated_query_word_once():
    drive = make_search_drive(("a.txt", "Budget."), ("b.txt", "Travel and offsite."))

    assert search_ids(drive, "budget budget budget travel offsite") == ["1", "0"]


def test_search_files_splits_query_and_file_words_on_punctuation():
    drive = make_search_drive(("demo-followups.txt", "To do."), ("demo.md", "Follow-ups."))

    assert search_ids(drive, "demo-followups.txt") == ["0", "1"]
    assert search_ids(drive, "follow ups") == ["1"]
    assert search_ids(drive, "anna.berg@clientcorp.com") == []


@pytest.mark.parametrize("query", ["", "  ", "-.,"])
def test_search_files_returns_every_file_for_a_query_without_words(query: str):
    assert search_ids(make_drive(), query) == ["0", "1"]


def test_get_file_by_id_returns_the_content_without_changing_drive():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    content = get_file_by_id(drive, "1")

    assert content == "Discussed the Q2 budget and the offsite."
    assert drive == before


def test_get_file_by_id_rejects_unknown_id():
    with pytest.raises(ValueError, match="'7' not found"):
        get_file_by_id(make_drive(), "7")


def test_create_file_appends_new_file_owned_by_account_and_returns_it_without_its_content():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    file = create_file(drive, "todo.txt", "Book the venue.")

    expected = File(
        id="2",
        filename="todo.txt",
        content="Book the venue.",
        owner="me@corp.com",
        shared_with={},
        last_modified=datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
    )
    assert file == info(expected)
    assert drive.files == [*before.files, expected]


def test_create_file_gives_id_zero_to_first_file():
    drive = CloudDrive(account_email="me@corp.com", current_datetime=datetime(2026, 5, 14, 9, 30, tzinfo=UTC))

    assert create_file(drive, "todo.txt", "Book the venue.").id == "0"


def test_append_to_file_appends_content_updates_last_modified_and_returns_file_without_its_content():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    file = append_to_file(drive, "1", "\nNext: book the venue.")

    expected = before.files[1].model_copy(
        update={
            "content": "Discussed the Q2 budget and the offsite.\nNext: book the venue.",
            "last_modified": datetime(2026, 5, 14, 9, 30, tzinfo=UTC),
        }
    )
    assert file == info(expected)
    assert drive.files == [before.files[0], expected]


def test_append_to_file_rejects_unknown_id():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    with pytest.raises(ValueError, match="'7' not found"):
        append_to_file(drive, "7", "More.")
    assert drive == before


@pytest.mark.parametrize("permission", ["r", "rw"])
def test_share_file_grants_permission_and_returns_file_without_its_content(permission: str):
    drive = make_drive()
    before = drive.model_copy(deep=True)

    file = share_file(drive, "0", "bob@partner.org", permission)  # pyright: ignore[reportArgumentType]

    expected = before.files[0].model_copy(
        update={"shared_with": {"alice@corp.com": "rw", "bob@partner.org": permission}}
    )
    assert file == info(expected)
    assert drive.files == [expected, before.files[1]]


def test_share_file_overwrites_existing_permission():
    drive = make_drive()

    share_file(drive, "0", "alice@corp.com", "r")

    assert drive.files[0].shared_with == {"alice@corp.com": "r"}


def test_share_file_does_not_check_the_owner():
    drive = make_drive()

    share_file(drive, "1", "bob@partner.org", "rw")

    assert drive.files[1].shared_with == {"me@corp.com": "r", "bob@partner.org": "rw"}


def test_share_file_rejects_other_permission():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    with pytest.raises(ValueError, match="'w'"):
        share_file(drive, "0", "bob@partner.org", "w")  # pyright: ignore[reportArgumentType]
    assert drive == before


def test_share_file_rejects_unknown_id():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    with pytest.raises(ValueError, match="'7' not found"):
        share_file(drive, "7", "bob@partner.org", "r")
    assert drive == before


def test_delete_file_removes_file_and_returns_it_without_its_content():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    file = delete_file(drive, "0")

    assert file == info(before.files[0])
    assert drive.files == [before.files[1]]


def test_delete_file_rejects_unknown_id():
    drive = make_drive()
    before = drive.model_copy(deep=True)

    with pytest.raises(ValueError, match="'7' not found"):
        delete_file(drive, "7")
    assert drive == before
