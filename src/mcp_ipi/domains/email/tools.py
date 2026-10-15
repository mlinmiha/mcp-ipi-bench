"""Email tools that read and change an inbox.

The inbox is injected at runtime and not exposed to the LLM.
"""

from ..search import rank
from .models import Email, EmailInfo, Inbox


def get_received_emails(inbox: Inbox) -> list[EmailInfo]:
    """Return all received emails.

    Returns:
        Every received email, without its body.
    """
    return [_info(email) for email in inbox.received]


def get_read_emails(inbox: Inbox) -> list[EmailInfo]:
    """Return all read received emails.

    Returns:
        Every read received email, without its body.
    """
    return [_info(email) for email in inbox.received if email.read]


def get_unread_emails(inbox: Inbox) -> list[EmailInfo]:
    """Return all unread received emails.

    Returns:
        Every unread received email, without its body.
    """
    return [_info(email) for email in inbox.received if not email.read]


def search_emails(
    inbox: Inbox,
    query: str,
    sender: str | None = None,
) -> list[EmailInfo]:
    """Search received and sent emails.

    Returns every email whose subject or body contains at least one word of the
    query, ranked by how many distinct query words it contains, best matches
    first.

    Args:
        query: Words to look for in the subject or body, as whole words, case-insensitively.
        sender: Optional sender address used to filter the results.

    Returns:
        Each received or sent email matching the query and optional sender
        filter, without its body, best matches first.
    """
    emails = [
        email for email in [*inbox.received, *inbox.sent] if sender is None or email.sender.lower() == sender.lower()
    ]

    return [_info(email) for email in rank(query, emails, lambda email: f"{email.subject}\n{email.body}")]


def get_email_by_id(inbox: Inbox, email_id: str) -> str:
    """Return a received or sent email by its ID.

    Args:
        email_id: ID of the email to read.

    Returns:
        The email as text: its sender, recipients, cc, bcc, subject and date,
        then a blank line and its body.

    Raises:
        ValueError: If no email with the given ID exists.
    """
    for email in [*inbox.received, *inbox.sent]:
        if email.id == email_id:
            return _text(email)

    raise ValueError(f"Email with ID {email_id!r} not found")


def send_email(
    inbox: Inbox,
    recipients: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> EmailInfo:
    """Send an email from the inbox account.

    Args:
        recipients: Email addresses of the recipients. Must contain at least one.
        subject: The email subject.
        body: The email body.
        cc: Optional email addresses to receive a carbon copy.
        bcc: Optional email addresses to receive a blind carbon copy.

    Returns:
        The newly created sent email, without its body.

    Raises:
        ValueError: If no recipients are provided.
    """
    if not recipients:
        raise ValueError("Email must have at least one recipient")

    email = Email(
        id=_next_id(inbox),
        sender=inbox.account_email,
        recipients=recipients,
        cc=cc or [],
        bcc=bcc or [],
        subject=subject,
        body=body,
        timestamp=inbox.current_datetime,
        read=True,
    )

    inbox.sent.append(email)
    return _info(email)


def delete_email(inbox: Inbox, email_id: str) -> EmailInfo:
    """Delete an email from the inbox.

    The email may be either received or sent.

    Args:
        email_id: ID of the email to delete.

    Returns:
        The deleted email, without its body.

    Raises:
        ValueError: If no email with the given ID exists.
    """
    for folder in (inbox.received, inbox.sent):
        for index, email in enumerate(folder):
            if email.id == email_id:
                return _info(folder.pop(index))

    raise ValueError(f"Email with ID {email_id!r} not found")


def _info(email: Email) -> EmailInfo:
    """Return an email's metadata: everything but its body."""
    return EmailInfo(
        id=email.id,
        sender=email.sender,
        recipients=email.recipients,
        cc=email.cc,
        bcc=email.bcc,
        subject=email.subject,
        timestamp=email.timestamp,
        read=email.read,
    )


def _text(email: Email) -> str:
    """Return an email as text: a header of the non-empty fields, a blank line, then the body."""
    header = {
        "From": email.sender,
        "To": ", ".join(email.recipients),
        "Cc": ", ".join(email.cc),
        "Bcc": ", ".join(email.bcc),
        "Subject": email.subject,
        "Date": email.timestamp.strftime("%Y-%m-%d %H:%M"),
    }
    lines = [f"{name}: {value}" for name, value in header.items() if value]
    return "\n".join(lines) + "\n\n" + email.body


def _next_id(inbox: Inbox) -> str:
    """Generate the next available email ID.

    Returns:
        The next available numeric email ID as a string.
    """
    ids = [int(email.id) for email in [*inbox.received, *inbox.sent] if email.id.isdigit()]
    return str(max(ids, default=-1) + 1)
