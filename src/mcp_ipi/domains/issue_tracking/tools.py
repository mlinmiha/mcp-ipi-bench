"""Issue tracking tools that read and change a Jira project.

The tracker is injected at runtime and not exposed to the LLM.
"""

from typing import Literal

from ..search import rank
from .models import Comment, Issue, IssueInfo, Jira


def search_issues(
    jira: Jira,
    query: str,
    status: Literal["open", "in_progress", "done"] | None = None,
    assignee: str | None = None,
) -> list[IssueInfo]:
    """Search issues.

    Returns every issue whose summary or description contains at least one word of the query, ranked by how many
    distinct query words it contains, best matches first. Comments are not searched.

    To read an issue's description and comments, call `get_issue` with its key.

    Args:
        query: Words to look for in the summary or description, as whole words, case-insensitively. An empty query
            matches every issue.
        status: Only return issues with this status: "open", "in_progress" or "done". All statuses when omitted.
        assignee: Only return issues assigned to this email address. All assignees when omitted.

    Returns:
        Each issue matching the query, without its description and comments, best matches first.
    """
    issues = [
        issue
        for issue in jira.issues
        if (status is None or issue.status == status)
        and (assignee is None or (issue.assignee or "").lower() == assignee.lower())
    ]

    return [_info(issue) for issue in rank(query, issues, lambda issue: f"{issue.summary}\n{issue.description}")]


def get_issue(jira: Jira, key: str) -> str:
    """Return an issue with its comments by its key, as text.

    Args:
        key: Key of the issue to read, e.g. "NL-3".

    Returns:
        The issue as text: its key, summary, status, assignee and reporter, then a blank line, its description and
        each comment with its author and time, oldest first.

    Raises:
        ValueError: If no issue with the given key exists.
    """
    return _text(_find_issue(jira, key))


def create_issue(jira: Jira, summary: str, description: str, assignee: str | None = None) -> IssueInfo:
    """Create an open issue reported by the current user.

    Args:
        summary: One-line summary of the issue.
        description: Description of the issue.
        assignee: Email address of the person to assign the issue to. Unassigned when omitted.

    Returns:
        The newly created issue, without its description and comments.
    """
    issue = Issue(
        key=_next_key(jira),
        summary=summary,
        description=description,
        status="open",
        assignee=assignee,
        reporter=jira.current_user,
    )

    jira.issues.append(issue)
    return _info(issue)


def update_issue(
    jira: Jira,
    key: str,
    status: Literal["open", "in_progress", "done"] | None = None,
    assignee: str | None = None,
    summary: str | None = None,
) -> IssueInfo:
    """Change the status, assignee or summary of an issue; fields that are omitted stay unchanged.

    Args:
        key: Key of the issue to update, e.g. "NL-3".
        status: New status: "open", "in_progress" or "done".
        assignee: Email address of the new assignee.
        summary: New one-line summary.

    Returns:
        The updated issue, without its description and comments.

    Raises:
        ValueError: If no field is given, or no issue with the given key exists.
    """
    if status is None and assignee is None and summary is None:
        raise ValueError("Give at least one of status, assignee or summary")

    issue = _find_issue(jira, key)
    if status is not None:
        issue.status = status
    if assignee is not None:
        issue.assignee = assignee
    if summary is not None:
        issue.summary = summary
    return _info(issue)


def add_comment(jira: Jira, key: str, body: str) -> IssueInfo:
    """Add a comment by the current user to an issue.

    Args:
        key: Key of the issue to comment on, e.g. "NL-3".
        body: Text of the comment.

    Returns:
        The issue commented on, without its description and comments.

    Raises:
        ValueError: If no issue with the given key exists.
    """
    issue = _find_issue(jira, key)
    comment = Comment(id=_next_comment_id(jira), author=jira.current_user, body=body, created_at=jira.current_datetime)

    issue.comments.append(comment)
    return _info(issue)


def _info(issue: Issue) -> IssueInfo:
    """Return an issue's metadata: everything but its description and comments."""
    return IssueInfo(
        key=issue.key,
        summary=issue.summary,
        status=issue.status,
        assignee=issue.assignee,
        reporter=issue.reporter,
    )


def _text(issue: Issue) -> str:
    """Return an issue as text: a header of the non-empty fields, a blank line, the description, then the comments."""
    header = {
        "Key": issue.key,
        "Summary": issue.summary,
        "Status": issue.status,
        "Assignee": issue.assignee,
        "Reporter": issue.reporter,
    }
    lines = [f"{name}: {value}" for name, value in header.items() if value]
    comments = [
        f"\n\nComment by {comment.author}, {comment.created_at.strftime('%Y-%m-%d %H:%M')}:\n{comment.body}"
        for comment in issue.comments
    ]
    return "\n".join(lines) + "\n\n" + issue.description + "".join(comments)


def _find_issue(jira: Jira, key: str) -> Issue:
    """Find an issue by its key.

    Args:
        key: Key of the issue to find.

    Returns:
        The issue.

    Raises:
        ValueError: If no issue with the given key exists.
    """
    for issue in jira.issues:
        if issue.key == key:
            return issue

    raise ValueError(f"Issue with key {key!r} not found")


def _next_key(jira: Jira) -> str:
    """Generate the next available issue key.

    Returns:
        The key `<project>-<n>`, where `n` is one more than the highest number in the project.
    """
    prefix = f"{jira.project}-"
    numbers = [int(issue.key.removeprefix(prefix)) for issue in jira.issues if issue.key.startswith(prefix)]
    return f"{prefix}{max(numbers, default=0) + 1}"


def _next_comment_id(jira: Jira) -> str:
    """Generate the next available comment ID, unique across all issues.

    Returns:
        The next available numeric comment ID as a string.
    """
    ids = [int(comment.id) for issue in jira.issues for comment in issue.comments if comment.id.isdigit()]
    return str(max(ids, default=-1) + 1)
