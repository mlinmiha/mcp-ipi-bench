"""The Workspace suite: email, web, cloud storage, calendar and issue tracking over one shared environment, with its
tasks."""

from pathlib import Path

from mcp_ipi.domains import CALENDAR, CLOUD_STORAGE, EMAIL, ISSUE_TRACKING, WEB

from ..suite import Suite
from .environment import WorkspaceEnvironment
from .injection_tasks import INJECTION_TASKS
from .policy import security_policy
from .user_tasks import USER_TASKS

WORKSPACE = Suite(
    name="workspace",
    domains=(EMAIL, WEB, CLOUD_STORAGE, CALENDAR, ISSUE_TRACKING),
    environment_cls=WorkspaceEnvironment,
    data_path=Path(__file__).parent / "data",
    user_name="Daniel Hartmann",
    user_tasks=USER_TASKS,
    injection_tasks=INJECTION_TASKS,
    security_policy=security_policy,
)
