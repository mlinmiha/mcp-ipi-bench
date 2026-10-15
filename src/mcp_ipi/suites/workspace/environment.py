"""The Workspace environment: one field per domain, named after its component."""

from pydantic import BaseModel

from mcp_ipi.domains.calendar import Calendar
from mcp_ipi.domains.cloud_storage import CloudDrive
from mcp_ipi.domains.email import Inbox
from mcp_ipi.domains.issue_tracking import Jira
from mcp_ipi.domains.web import Web


class WorkspaceEnvironment(BaseModel):
    inbox: Inbox
    web: Web
    cloud_drive: CloudDrive
    calendar: Calendar
    jira: Jira
