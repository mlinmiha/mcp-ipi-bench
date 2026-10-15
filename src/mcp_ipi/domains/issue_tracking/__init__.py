"""Issue tracking domain with the Jira component and its tools."""

from ..base import Domain
from .models import Comment, Issue, IssueInfo, Jira
from .tools import add_comment, create_issue, get_issue, search_issues, update_issue

ISSUE_TRACKING = Domain(
    name="issue_tracking",
    component="jira",
    model=Jira,
    tools=(search_issues, get_issue, create_issue, update_issue, add_comment),
)

__all__ = ["ISSUE_TRACKING", "Comment", "Issue", "IssueInfo", "Jira"]
