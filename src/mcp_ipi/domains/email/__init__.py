"""Email domain with the inbox component and its tools."""

from ..base import Domain
from .models import Email, EmailInfo, Inbox
from .tools import (
    delete_email,
    get_email_by_id,
    get_read_emails,
    get_received_emails,
    get_unread_emails,
    search_emails,
    send_email,
)

EMAIL = Domain(
    name="email",
    component="inbox",
    model=Inbox,
    tools=(
        get_received_emails,
        get_read_emails,
        get_unread_emails,
        search_emails,
        get_email_by_id,
        send_email,
        delete_email,
    ),
)

__all__ = ["EMAIL", "Email", "EmailInfo", "Inbox"]
