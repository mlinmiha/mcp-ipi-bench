[EN](README.md) | [SI](README.si.md)

# Načrt analize

Kaj `ipi analyze` izračuna za vsako od treh hipotez magistrskega dela. Vsak test pripada natanko eni hipotezi, vse,
kar ne pripada nobeni, pa je našteto pod [Opisne tabele](#opisne-tabele). Načrt je določen pred glavno serijo
zagonov (*sweep*); nič v njem ni izbrano po pogledu v njene rezultate.

Stanje: vse tabele so narejene (`tables.py`): opisne in spodnje tabele hipotez, `h1_attacks`, `h1_attack_pairs`,
`h2_defenses`, `h2_defenses_by_attack`, `h3_coverage`, `h3_levels`, `h3_injection_tasks` in `h3_breadth`.

## Podatki

- **Enota.** En varnostni zagon: model × obramba × napad × par, z binarnim izidom `security` (true = napad je uspel).
  ASR je delež zagonov, pri katerih je security true, med zagoni brez napake zagona.
- **En zagon na enoto.** Vsaka enota se požene enkrat pri temperaturi 0, zato ni ponovitev, ki bi jih povprečili.
  250 parov uravnotežene podmnožice je vzorec; istih 250 se požene v vsaki konfiguraciji, zato je vsaka primerjava
  parna po paru.
- **Uporabljeni zagoni.** Samo varnostni zagoni v uravnoteženi podmnožici. Napake zagonov so izpuščene; primerjava
  uporabi par le, kadar so vsi njegovi zagoni v tej primerjavi brez napake.
- **Modeli so fiksni dejavnik.** Pet modelov je premalo za oceno variabilnosti med modeli, zato se noben rezultat ne
  posplošuje na druge modele. Rezultat je podan za vsak model posebej ali za navedeno množico modelov.
- **Odvisnost.** Pari med seboj niso neodvisni: vsaka uporabniška naloga je v 5 parih, vsaka naloga vrivanja pa v
  10. Testi obravnavajo par kot neodvisno enoto; intervali velikosti učinka ne (glej spodaj).

### Skupne definicije

- **Značilnost.** α = 0,05, dvostransko, za vsak test. Hipoteza, ki navaja smer, zahteva tudi, da ocena kaže v to
  smer.
- **Večkratne primerjave.** Holmov popravek znotraj primarnih testov ene hipoteze in posebej znotraj njenih
  sekundarnih testov. Med hipotezami se nič ne popravlja. Vsaka tabela poda surovi p, po Holmu popravljeni p in
  število testov v svoji družini.
- **Eksaktni parni test.** Za dva pogoja na istih parih: `b` = pari, kjer je prvi slabši (več uspešnih napadov),
  `c` = pari, kjer je slabši drugi, p = eksaktni dvostranski binomski p za min(b, c) od b + c pri 0,5 (`_mcnemar`). Z
  enim napadom na par je to McNemarjev test. Z več napadi je vrednost para število uspešnih napadov med njimi, zato
  par ostane enota in se napadi na en par ne štejejo kot neodvisni.
- **Velikost učinka.** Razlika obeh ASR v odstotnih točkah, s 95-odstotnim intervalom iz gručnega zankanja
  (cluster bootstrap) po uporabniških nalogah: 50 uporabniških nalog se vzorči s ponavljanjem, vsaka z vsemi svojimi
  pari, 10 000-krat s stalnim semenom, interval pa je od 2,5. do 97,5. percentila. Relativno zmanjšanje,
  1 − ASR / ASR izhodišča, je podano ob njej in je prazno, kadar je ASR izhodišča 0.
- **Upoštevani modeli.** GPT-5.4 mini, Qwen in Mistral Medium 3: modeli, ki imajo pri izhodišču v
  `sweeps/pilot-attacks.yaml` vsaj dva napada z ASR 20 % ali več. Pravilo in seznam izhajata iz pilota, ne iz
  glavne serije zagonov, zato izbira ne pristrani njenih ocen. Gemini (največ 7 %) in DeepSeek (največ 12 %) nista
  upoštevana.
- **Raven obrambe.** Raven vsebine: `spotlighting`, `sanitizer` (spremenita, kaj model prebere). Raven dejanj:
  `tool-filter`, `security-policy` (omejita, kaj model lahko pokliče). Raven izhaja iz tega, kako obramba deluje, ne
  iz njenih rezultatov.
- **Pokrit par.** Določen iz referenčnih rešitev zbirke, brez modela:
  - `security-policy` pokrije par, kadar politika blokira klic iz referenčne rešitve naloge vrivanja: 12 od 25 nalog
    vrivanja, 120 od 250 parov; 130 jih ni pokritih.
  - `tool-filter` pokrije par, kadar referenčna rešitev naloge vrivanja pokliče orodje, ki ga referenčna rešitev
    uporabniške naloge ne pokliče, zato ga filter, ki ohrani samo orodja uporabniške naloge, odstrani: 240 od 250
    parov; 10 jih ni pokritih.
- **Moč.** Vzorec je določen na 250 parov, zato se velikost vzorca ne izpeljuje. Eksaktni parni test lahko doseže
  p < 0,05 le z vsaj 6 različnimi pari, vsemi v eno smer, in prestane Holmov popravek le z vsaj 8 (6 testov) ali 9
  (12 testov). Celica z manj različnimi pari ne more biti značilna in je tako tudi navedena.

## H1 – tehnike napada se razlikujejo

> Stopnja uspešnosti napadov (ASR) pri agentu brez obrambe se statistično značilno razlikuje glede na uporabljeno
> tehniko napada, pri čemer se upoštevajo razlike med uporabljenimi modeli.

**Zagoni.** Samo izhodišče, vsi štirje napadi, vseh pet modelov: 5 × 4 × 250 = 5 000 zagonov.

**Primarni test.** Cochranov Q za vsak model, čez štiri napade na parih, kjer so vsi štirje zagoni brez napake:
Q = (k − 1)(k ΣCⱼ² − N²) / (kN − ΣRᵢ²), kjer je k = 4 napadi, Cⱼ število uspehov napada j, Rᵢ število uspehov na paru
i in N vsi uspehi; p iz porazdelitve χ² s k − 1 prostostnimi stopnjami, in p = 1, kadar se noben par ne razlikuje med
napadi. Testiranje znotraj vsakega modela je način, kako se upoštevajo razlike med modeli: splošna raven modela
nikoli ne vstopi v njegov test. 5 testov, Holm.

**Odločitev.** H1 drži za model, kadar je njegov popravljeni p < 0,05. Delo navede, pri koliko od petih modelov drži;
H1, kot je zapisana, je podprta, kadar drži pri vsaj enem, število pa pove, kako splošno je to.

**Sekundarno.**
- Vsaka dva napada, primerjana z eksaktnim parnim testom, za vsak model: 6 × 5 = 30 testov, Holm, z velikostjo
  učinka.
- Cochranov Q samo čez tri napade glavne serije zagonov (`fake-completion`, `task-aligned`, `tool-notice`), za vsak model,
  5 testov. `direct-instruction` je bil ohranjen kot znano šibek napad, zato test čez štiri večinoma potrdi to izbiro;
  ta test pa sprašuje, ali se močni napadi razlikujejo.
- Rang štirih napadov po ASR pri vsakem modelu, kot opis interakcije model × napad. Ni testiran.

**Robustnost.**
- Primarni test na 150 parih, katerih uporabniška naloga ni bila v `sweeps/pilot-attacks.yaml` (peta do deseta
  uporabniška naloga vsake domene). Napadi so bili izbrani na preostalih 100.
- Primarni test samo na zmožnih parih.
- Model, katerega Q ima v parih, ki se razlikujejo, manj kot 24 celic (različni pari × k), je označen: približek s
  χ² je tam slab.

**Tabela.** `h1_attacks` (množica zagonov × model: n, ASR za vsak napad, Q, p, popravljeni p) in `h1_attack_pairs` (model × napad ×
napad).

## H2 – obrambe znižajo ASR

> Pri modelih, pri katerih napadi brez obrambe dosegajo uspešnost, obrambni mehanizmi statistično značilno zmanjšajo
> stopnjo uspešnosti napadov (ASR) v primerjavi z agentom brez obrambe.

**Zagoni.** Upoštevani modeli, trije napadi, ki se poženejo z vsako obrambo, izhodišče in štiri obrambe:
3 × 3 × 5 × 250 = 11 250 zagonov.

**Primarni test.** Vsaka obramba proti izhodišču, za vsak upoštevani model, z eksaktnim parnim testom čez tri napade
na vseh 250 parih. 3 modeli × 4 obrambe = 12 testov, Holm.

**Odločitev.** Obramba zniža ASR pri modelu, kadar je njen popravljeni p < 0,05 in je njen ASR pod ASR izhodišča. H2
drži za obrambo, kadar je tako pri vseh treh upoštevanih modelih, in drži, kot je zapisana, kadar drži za vse štiri
obrambe. Sicer delo navede, za katere obrambe in modele drži.

**Velikost učinka.** Absolutno in relativno zmanjšanje ASR za model × obramba, kot je določeno zgoraj.

**Sekundarno.** Ista primerjava za vsak napad: model × napad × obramba z McNemarjevim testom, 36 testov na
upoštevanih modelih, Holm.

**Robustnost.**
- Primarni test na vseh petih modelih (20 testov), da se pokaže, da sklep ne sloni na izbiri modelov.
- Primarni test samo na zmožnih parih.
- Primarni test, pri katerem se vsaka napaka zagona šteje kot neuspel napad, ker se napake med obrambami razlikujejo.

**Tabela.** `h2_defenses` (množica zagonov × model × obramba) in `h2_defenses_by_attack` (model × napad ×
obramba).

## H3 – širina in moč obramb

> Obrambe na ravni vsebine zmanjšujejo stopnjo uspešnosti napadov (ASR) v širšem naboru scenarijev napada, vendar je
> njihov učinek omejen. Obrambe na ravni dejanj zmanjšujejo ASR le v scenarijih, ki jih pokrivajo, vendar v teh
> dosegajo večje zmanjšanje ASR kot obrambe na ravni vsebine.

H3 v nobenem testu ne primerja obrambe z izhodiščem; to je H2. Obrambo na ravni dejanj primerja neposredno z obrambo
na ravni vsebine, na parih, ki jih obramba na ravni dejanj pokriva, in na tistih, ki jih ne. To, da je ena obramba
proti izhodišču »značilna«, druga pa »ni značilna«, ne bi pokazalo, da se razlikujeta med seboj.

**Zagoni.** Upoštevani modeli, trije napadi, ki se poženejo z vsako obrambo, in štiri obrambe. Vrednost para pri
obrambi je število uspešnih napadov čez tri modele in tri napade (0 do 9).

**Primarni testi.** Eksaktni parni test med obrambo na ravni dejanj in obrambo na ravni vsebine. 6 testov, Holm.

| Trditev | Pari                                           | Primerjano                                        | H3 napoveduje           |
|---------|------------------------------------------------|---------------------------------------------------|-------------------------|
| moč     | 120 parov, ki jih pokriva `security-policy`    | `security-policy` s `spotlighting`, s `sanitizer` | `security-policy` nižji |
| moč     | 240 parov, ki jih pokriva `tool-filter`        | `tool-filter` s `spotlighting`, s `sanitizer`     | `tool-filter` nižji     |
| širina  | 130 parov, ki jih `security-policy` ne pokriva | `spotlighting`, `sanitizer` s `security-policy`   | raven vsebine nižja     |

`tool-filter` pusti nepokritih 10 parov, kar je premalo za test, zato je njegova trditev o širini samo opisana.

**Odločitev.** Moč drži za obrambo na ravni dejanj, kadar imata oba njena testa popravljeni p < 0,05 in je njen ASR
nižji. Širina drži, kadar to velja za oba testa širine in je nižja obramba na ravni vsebine. H3 drži, kot je
zapisana, kadar moč drži za obe obrambi na ravni dejanj in drži širina.

**Ocene, ki niso testirane.**
- *Samo tam, kjer pokriva.* Zmanjšanje ASR glede na izhodišče za vsako obrambo na ravni dejanj na njenih pokritih in
  nepokritih parih, z intervali. »Brez učinka tam, kjer ne pokriva« se trdi le, kadar cel interval zmanjšanja na
  nepokritih parih leži znotraj ±10 odstotnih točk; test, ki ni značilen, tega ne pokaže.
- *Omejen učinek.* ASR, ki ostane pri vsaki obrambi na ravni vsebine na vseh parih, z Wilsonovim intervalom in
  relativnim zmanjšanjem.
- *Pokritost po zasnovi.* Delež parov, ki jih pokriva vsaka obramba na ravni dejanj: 120 / 250 in 240 / 250.
- *Širina po nalogah vrivanja.* Za vsako obrambo delež od 25 nalog vrivanja, katerih ASR pade za vsaj 10 odstotnih
  točk glede na izhodišče, med nalogami vrivanja z ASR izhodišča vsaj 10 %; tudi pri 5 in 20 točkah. Vsaka naloga
  vrivanja ima 90 zagonov na obrambo (10 parov × 3 napadi × 3 modeli).

**Sekundarno.** Šest primarnih testov za vsak upoštevani model: 18 testov, Holm.

**Robustnost.**
- Primarni testi na vseh petih modelih.
- Primarni testi na parih, ki so zmožni za vse tri upoštevane modele.
- Primarni testi na parih, kjer je napad pri izhodišču uspel vsaj enkrat, ker par, na katerem ne uspe noben napad,
  ne more pokazati razlike.

**Tabela.** `h3_levels` (množica zagonov × model × trditev × obramba na ravni dejanj × obramba na ravni vsebine, z
modelom `pooled` v vseh vrsticah razen sekundarnih: pari, oba ASR, b, c, p, popravljeni p, razlika z intervalom),
`h3_coverage` (obramba × pokritost: pari, zagoni, ASR izhodišča, ASR, zmanjšanje z intervalom, ali ta leži znotraj
meje), `h3_injection_tasks` (obramba × naloga vrivanja: zagoni, ASR izhodišča, ASR, zmanjšanje) in `h3_breadth` (obramba:
njena raven, naloge vrivanja pri vsakem pragu in tiste med njimi, ki so zmanjšane za vsaj toliko, z deležem, ter ASR,
ki ostane na vseh parih, z Wilsonovim intervalom in relativnim zmanjšanjem).

## Opisne tabele

Te opisujejo zagone in ne testirajo nobene hipoteze: `utility`, `security`, združene tabele `security_by_*`,
`domains`, `difficulty`, `injection_checks`, `cost`, `subset_validation`, `errors` in `paired` (koliko uporabnosti
obramba stane). Njihovi stolpci so določeni v `docs/PROJECT.md`.

## Ni narejeno

- **Brez logističnega modela z mešanimi učinki.** Z enim zagonom na enoto celice z ASR 0 % ali blizu tega
  (`direct-instruction`, Gemini) skoraj popolnoma ločijo izid, zaradi česar so njegove ocene nestabilne, potreboval pa
  bi tudi drugo programsko orodje. Eksaktni parni testi uporabijo parnost, ki jo zasnova že ima. `security.csv` in
  datoteke zagonov zadoščajo, da se tak model prilagodi zunaj `ipi analyze`.
- **Brez simulacije moči.** Število parov je določila zasnova; najmanjši zaznavni rezultat je naveden pod Moč.
- **Brez empirične pokritosti za `tool-filter`.** Katera orodja je filter ohranil, ni v datoteki zagona, zato je
  pokritost samo po zasnovi.
