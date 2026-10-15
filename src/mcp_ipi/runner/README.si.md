[EN](README.md) | [SI](README.si.md)

# runner

Izvaja zagone benchmarka. En zagon je model z obrambo na uporabniški nalogi, v varnostnem zagonu pa še pod napadom z
nalogo vrivanja. Njegov rezultat se zapiše v eno datoteko zagona, ki je vir vsake metrike.

| Datoteka      | Kaj vsebuje                                                                                                                   |
|---------------|-------------------------------------------------------------------------------------------------------------------------------|
| `runner.py`   | `run_task` (en ocenjen zagon), `run` (en zagon, zapisan v svojo datoteko zagona), `benchmark` (zagoni ene vrste zagona)       |
| `run_file.py` | `RunResult`, polja datoteke zagona, in pot datoteke zagona                                                                    |
| `sweep.py`    | `Sweep`: datoteka serije zagonov (*sweep*), njena razširitev v zagone po vrstah zagona in izpis števila zagonov (`--dry-run`) |
| `show.py`     | Besedilo ukaza `ipi show`: zagon v celoti, tabela zagonov, vrstica povzetka                                                   |

## Zagon

1. Sestavi se besedilo napada in vstavi v vektorje vrivanja, ki jih uporabniška naloga prebere (samo varnostni zagoni).
2. Naložita se dve kopiji okolja: ena ostane začetno okolje, na drugi dela agent.
3. Cevovod obrambe izvede poziv uporabniške naloge prek MCP.
4. Preverjanje uporabniške naloge da `utility`, preverjanje naloge vrivanja da `security` (true = napad je uspel).

## Datoteke zagonov

```
<logdir>/<pipeline>/<suite>/<user_task>/<attack>/<injection_task>.json
runs-pilot/openai_gpt-5.4-mini-spotlighting/workspace/cloud_storage_user_task_2/tool-notice/web_injection_task_2.json
```

Zagon, katerega datoteka obstaja in nima napake, se preskoči, zato se prekinjena serija zagonov nadaljuje tako,
da se zažene znova.

## Primer

```sh
# Samo izpiše, koliko zagonov ima serija; modela ne kliče
uv run ipi sweep sweeps/main.yaml --dry-run

# Požene vse zagone serije
uv run --env-file .env ipi sweep sweeps/main.yaml

# Izpiše eno vrstico na zagon in vrstico povzetka
uv run ipi show --summary runs/<pipeline>/workspace/*/none/none.json
```
