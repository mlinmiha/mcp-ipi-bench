[EN](README.md) | [SI](README.si.md)

# domains

Domena je ena komponenta okolja, njen model Pydantic in orodja, ki delajo na njej (`Domain` v `base.py`). Koda tukaj
je navaden Python: ne pozna MCP, zbirk ali benchmarka.

| Domena           | Komponenta    | Model        |
|------------------|---------------|--------------|
| `email`          | `inbox`       | `Inbox`      |
| `web`            | `web`         | `Web`        |
| `cloud_storage`  | `cloud_drive` | `CloudDrive` |
| `calendar`       | `calendar`    | `Calendar`   |
| `issue_tracking` | `jira`        | `Jira`       |

Vsaka domena je paket z datotekami `models.py`, `tools.py` in `__init__.py`, ki določi opisnik domene, npr. `EMAIL`.
`search.py` vsebuje `rank`, pravilo razvrščanja, ki je skupno iskalnim orodjem.

## Orodja

Orodje je funkcija, katere prvi argument je komponenta njene domene. Njen docstring je opis, ki ga vidi model, njeni
drugi argumenti pa postanejo vhodna shema orodja.

```python
def get_unread_emails(inbox: Inbox) -> list[EmailInfo]:
    """Return all unread received emails.

    Returns:
        Every unread received email, without its body.
    """
    return [_info(email) for email in inbox.received if not email.read]
```
