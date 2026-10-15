[EN](README.md) | [SI](README.si.md)

# defenses

Obramba je funkcija `<name>_pipeline(llm, policy)`, ki sestavi agentov cevovod z vgrajeno obrambo. Vsaka je
izhodiščni cevovod z enim spremenjenim delom. Obrambe niso odvisne od zbirke; politiko zbirke dobijo kot argument.

| Obramba           | Raven   | Kaj spremeni                                                                           |
|-------------------|---------|----------------------------------------------------------------------------------------|
| `none`            |         | Nič: izhodišče                                                                         |
| `spotlighting`    | vsebina | Vsak rezultat orodja ovije v oznaki `<TOOL_RESULT>`, ki ju razloži sistemski poziv     |
| `sanitizer`       | vsebina | Agentov model iz vsakega rezultata orodja odstrani navodila, preden ga agent prebere   |
| `tool-filter`     | dejanja | Agentov model ohrani samo orodja, ki jih naloga potrebuje, preden se preberejo podatki |
| `security-policy` | dejanja | Vsak klic orodja se preveri po politiki zbirke in blokira, če ga ta prepoveduje        |

`DEFENSES` vsebuje vsako funkcijo pod imenom obrambe.

## Primer

```python
pipeline = DEFENSES["spotlighting"](llm, suite.security_policy)
```
