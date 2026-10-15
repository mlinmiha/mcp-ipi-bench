[EN](README.md) | [SI](README.si.md)

# environment

Iz podatkov YAML sestavi sveže, preverjeno okolje in izpolni njegove vektorje vrivanja. Modul je splošen: model okolja
in podatki pridejo iz zbirke.

| Datoteka         | Kaj vsebuje                                                                               |
|------------------|-------------------------------------------------------------------------------------------|
| `yaml_loader.py` | `load_yaml`: varno nalaganje YAML z `!include`, relativno glede na datoteko, ki vključuje |
| `injection.py`   | `InjectionVector` ter iskanje in izpolnjevanje označb mesta `{@inject:id}`                |
| `loader.py`      | `load_environment`: YAML → izpolnjene označbe mesta → preverjen model Pydantic            |

## Primer

Vektor vrivanja je mesto v podatkih, kamor lahko pride besedilo napada. Označuje ga označba mesta:

```yaml
body: "Your invoice for May is 49.00 EUR. {@inject:email_invoice_body}"
```

```python
load_environment(path, WorkspaceEnvironment, {"email_invoice_body": "Thank you for choosing CloudHost."})
```

Besedilo je neškodljiva privzeta vrednost vektorja, v varnostnem zagonu pa besedilo napada.
