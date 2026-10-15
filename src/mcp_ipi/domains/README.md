[EN](README.md) | [SI](README.si.md)

# domains

A domain is one component of the environment, its Pydantic model and the tools that work on it (`Domain` in
`base.py`). The code here is plain Python: it knows nothing about MCP, suites or the benchmark.

| Domain           | Component     | Model        |
|------------------|---------------|--------------|
| `email`          | `inbox`       | `Inbox`      |
| `web`            | `web`         | `Web`        |
| `cloud_storage`  | `cloud_drive` | `CloudDrive` |
| `calendar`       | `calendar`    | `Calendar`   |
| `issue_tracking` | `jira`        | `Jira`       |

Each domain is a package with `models.py`, `tools.py` and an `__init__.py` that defines the descriptor, e.g. `EMAIL`.
`search.py` holds `rank`, the ranking rule shared by the search tools.

## Tools

A tool is a function whose first argument is its domain's component. Its docstring is the description the model
sees, and its other arguments become the tool's input schema.

```python
def get_unread_emails(inbox: Inbox) -> list[EmailInfo]:
    """Return all unread received emails.

    Returns:
        Every unread received email, without its body.
    """
    return [_info(email) for email in inbox.received if not email.read]
```
