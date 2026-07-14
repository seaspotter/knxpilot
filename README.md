# KNXpilot

Planungswerkzeug für KNX-Installationen, entwickelt anhand echter ETS6-Projekte.
Für Elektriker/Systemintegratoren, die mehrere Projekte parallel planen und dabei
durchgängige Adressierungs- und Namenskonventionen einhalten wollen. Deckt den
Weg von der ersten Raumplanung bis zur fertigen ETS6-Gruppenadressen-CSV, der
Aktoren-Verdrahtungsliste (Abgangsliste) und der Kundendokumentation
(Pflichtenheft) ab.

**Kernablauf:** Geschosse → Räume → Punkte (Licht / Steckdosen / Fenster /
Heizung) → fertig. Zentral- und Allgemeinfunktionen (Datum/Uhrzeit,
Wetterstation, "alle Lichter aus" je Geschoss usw.) werden automatisch aus
Vorlagen erzeugt — normalerweise muss man das pro Projekt gar nicht anfassen.

## Schnellstart

**Voraussetzungen:** Docker mit Compose-Plugin, sowie `git`.

```bash
git clone https://github.com/seaspotter/knxpilot.git
cd knxpilot
docker compose up -d --build
```

Danach `http://<host>:8000` öffnen.

**Beim ersten Start:**
- Kategorien, Punkttypen und Zentral-/Allgemeinfunktions-Vorlagen sind
  bereits mit sinnvollen Standardwerten vorbelegt (siehe Setup-Tab unten).
- Der Geräte-Tab wird automatisch mit einem Startkatalog gängiger
  KNX-Geräte gefüllt (siehe Geräte-Tab unten).
- Es gibt **keine Benutzerauthentifizierung** — nur im eigenen internen
  Netzwerk betreiben, nie direkt ans Internet exponieren.

Für eine Proxmox/LXC-Bereitstellung siehe *Bereitstellung auf Proxmox*
weiter unten; für spätere Updates den **Update**-Tab in der App verwenden
(siehe unten) oder manuell `git pull` + Neustart.

## Adressierungsmodell (entspricht Ihren echten Projekten)

| KNX-Ebene       | Zuordnung |
|-----------------|-----------|
| Hauptgruppe     | Funktionskategorie: `Allgemein, Beleuchtung, Steckdosen, Heizung, Rollo, Tore` |
| Mittelgruppe    | `Zentralfunktionen` + eine je Geschoss |
| Untergruppe     | Ein Adressblock je physischem Punkt: `{Raum} {Label} {Suffix}` |

Jeder Punkt reserviert einen **festen Adressblock** (Standard 5, oder 10 bei
Jalousien mit Lamelle) und füllt ungenutzte Plätze mit `res` für spätere
Erweiterungen auf — genau wie in Ihren bestehenden Projekten.

## GA-CSV-Format für ETS6

Tab-getrennt, jedes Feld in Anführungszeichen, mit Kopfzeile, Spalten:
```
Main  Middle  Sub  Address  Central  Unfiltered  Description  DatapointType  Security
```
DPTs werden als `DPST-x-y` geschrieben, `Security` ist immer `Auto`. Byte für
Byte gegen mehrere echte ETS6-Exporte geprüft, daher sollte der Import direkt
funktionieren: Rechtsklick auf **Gruppenadressen** → **Gruppenadressen
importieren**.

Falls sich Ihre Konventionen in ETS jemals ändern und Importe anfangen,
Zeilen zu überspringen: ein kleines Testprojekt exportieren und mit der
Ausgabe des Tools vergleichen — der CSV-Schreiber ist in `export_csv()`
in `app/routers/projects.py` isoliert.

## Die vier Tabs

- **Projekte** — Projekte anlegen/suchen/bearbeiten und öffnen; ein geöffnetes
  Projekt zeigt einen Arbeitsbereich mit vier Unterreitern (Gruppenadressen,
  Abgangsliste, Geräteplanung, Pflichtenheft), die alle am selben Projekt
  arbeiten.
- **Geräte** — globaler Gerätekatalog (Aktoren, Sensoren, Bedienelemente
  usw.), gemeinsam für alle Projekte genutzt.
- **Setup** — Kategorien, Punkttypen und Zentral-/Allgemeinfunktions-
  Vorlagen; im Alltag selten angefasst, bereits vorbelegt.
- **Update** — prüft auf Wunsch, ob auf GitHub eine neuere Version vorliegt,
  und installiert sie.

### Projekte

**Projektliste** (Standardansicht): Projekt anlegen mit Name, Kunde, Standort,
Status (In Planung / In Ausführung / Abgeschlossen / Pausiert), Bestellnummer
und Kommentar — alle Felder ausser Name optional. Ein Suchfeld filtert live
nach allen diesen Feldern; Kunde/Standort/Status/Bestellnummer erscheinen als
Badges neben jedem Projektnamen. **⭱ Aus Sicherung wiederherstellen (JSON)**
legt aus einer zuvor exportierten Datei ein neues Projekt an (siehe
Gruppenadressen unten) — existiert bereits ein Projekt mit gleichem Namen,
wird der Import als "<Name> (imported)" gespeichert statt es zu überschreiben.

**Öffnen** eines Projekts zeigt dessen Arbeitsbereich: oben die
Projekt-Metadaten mit **Bearbeiten**-Button (ändert Name/Kunde/Standort/
Status/Bestellnummer/Kommentar nachträglich), daneben **⭳ Sichern (JSON)**
und **× Schliessen**. **× Schliessen** kehrt zur Projektliste zurück, ohne
etwas zu löschen — beim nächsten Öffnen startet der Arbeitsbereich wieder
beim Unterreiter Gruppenadressen.

#### Gruppenadressen

- Geschosse (Stockwerke) hinzufügen; ein Geschoss als **Aussen/unbeheizt**
  markieren (z.B. "Aussen", "Garage"), wenn es von entsprechend markierten
  Vorlagen ausgeschlossen werden soll.
- Räume je Geschoss hinzufügen.
- Für jeden Raum Punkte hinzufügen: Punkttyp wählen (z.B. "Licht (Dimmen)"),
  ein Label vergeben (z.B. "Spots", "Decke", "Nord" für ein Fenster), bei
  Bedarf eine Anzahl für mehrere gleiche auf einmal, und **+BWM** ankreuzen,
  falls dieser Punkt eine Bewegungsmelder-Adresse braucht.
- **Alles Spezielle** (Einzel-Szene, spezielle Zentralgruppe für einen
  bestimmten Raum wie "Kind1 Zentral") kommt unter **Sonder-/
  Zusatzadressen** — Kategorie wählen, festlegen ob es zu
  `Zentralfunktionen` oder einem bestimmten Geschoss gehört, benennen und
  die Datenpunkte angeben.
- **Vorschau** zur Kontrolle, dann **CSV für ETS6 herunterladen**.
- **⭳ Sichern (JSON)** speichert die komplette Projektdefinition (Metadaten,
  Geschosse, Räume, Punkte, Sonderadressen) als `.json`-Datei — getrennt von
  der ETS-CSV, gedacht zum Sichern / Duplizieren / Umziehen eines Projekts
  zwischen Installationen. Beim Wiederherstellen werden Punkttypen/
  Kategorien per Name mit der Zielinstallation abgeglichen; was nicht
  übereinstimmt, wird übersprungen und gemeldet, nie einfach angenommen.

#### Abgangsliste

Sobald ein Projekt Räume und Punkte enthält, kennt das Tool bereits jeden
physischen Ausgang, der benötigt wird (jeder Schalt-, Dimm-, LED-, Jalousie-
und Heizkanal). Dieser Unterreiter macht daraus eine Verdrahtungsliste für
den Elektriker — getrennt von der ETS-Gruppenadressen-CSV: die eine dient
der Busprogrammierung, die andere der Schaltschrank-Verdrahtung.

1. Jeder Punkttyp hat einen **Kanaltyp** (z.B. `Schalten`, `Dimmen`, `LED`,
   `Rollo`, `Heizung`, `Tor`, siehe Setup-Tab) und **benötigte Kanäle**
   (meist 1).
2. Im Geräte-Tab die verwendeten Aktoren anlegen, mit einem **Type**, der
   zum Kanaltyp passt (siehe unten).
3. Die **Bedarfsübersicht** zeigt sofort, wie viele Kanäle je Geschoss und
   Kanaltyp tatsächlich benötigt werden (benötigt/zugeordnet/offen) — so
   lässt sich die richtige Aktorgrösse wählen, bevor überhaupt ein Aktor
   angelegt wird.
4. Die tatsächlich verbauten **Aktoren** hinzufügen (Aktortyp wählen, in
   welchem Geschoss/welcher UV er sitzt, Standortbezeichnung, physische
   KNX-Adresse wie `1.1.2`). Jeder Aktor zeigt eine kleine visuelle
   Kanalübersicht (grün = belegt mit Funktionsname beim Hovern, grau =
   frei).
5. Jeder **Abgang** (eine Zeile je benötigtem physischen Ausgang) erscheint
   darunter mit einer Auswahl aller Kanäle passender Aktoren. Einen manuell
   wählen, oder **Alle automatisch zuordnen** klicken, um jeden noch nicht
   zugeordneten Abgang dem ersten freien passenden Kanal zuzuweisen.
   **Automatisch zuordnen mischt dabei nie Geschosse** — ein Abgang im EG
   wird nur einem Aktor im EG zugeordnet, selbst wenn dessen Kanäle voll
   sind und ein Aktor im OG noch frei wäre. Aktoren ohne zugewiesenes
   Geschoss werden von der Automatik ebenfalls nicht verwendet; solche
   Fälle bitte manuell zuordnen.
6. **CSV herunterladen** exportiert eine Tabelle mit den Spalten
   `Geschoss, Raum/UV, Aktor, Physikalische Adr., Kanal, Funktion` — jeder
   Kanal jedes Aktors wird aufgeführt, unbelegte mit `RESERVE` markiert.
   **PDF herunterladen** exportiert dieselben Daten als formatiertes, nach
   Geschoss und Aktor gegliedertes PDF (ein Geschoss pro Seite).

#### Geräteplanung

Getrennt von der Abgangsliste (die nur Aktoren mit physischen Kanälen
betrifft): hier wird festgelegt, welche Geräte — **jeder Gruppe**, also auch
Sensoren, Wetterstationen, Bedienelemente — in welchem Raum verbaut werden,
unabhängig davon ob dafür eine Gruppenadresse oder ein Aktorkanal existiert.

1. Für jeden Raum Geräte mit Anzahl und optionaler Notiz hinzufügen (z.B.
   "2× Bewegungsmelder — Ecken", "1× Touchpanel — Eingang").
2. Oben erscheint automatisch eine **Stückliste** — die Gesamtanzahl jedes
   benötigten Geräts über das ganze Projekt hinweg, nach Gruppe sortiert.
   Praktisch für Bestellung oder Angebotskalkulation.
3. **PDF herunterladen** exportiert diese Stückliste als Bestellliste, plus
   eine Aufschlüsselung je Raum.

#### Pflichtenheft

Dokumentiert, was für das Projekt tatsächlich vereinbart/umgesetzt wurde —
gedacht als Referenz für Kunde und Elektriker, getrennt von den technischen
GA-/Verdrahtungsdetails. Eine Textvorschau zeigt sofort, was im PDF stehen
wird; **PDF herunterladen** erzeugt ein mehrseitiges Dokument mit den
geplanten Funktionen und Geräten je Geschoss/Raum, einer Übersicht der
Zentral-/Allgemeinfunktionen und der Geräte-Stückliste als Abschluss.

### Geräte

Globaler Gerätekatalog — **gemeinsam für alle Projekte**, unabhängig davon
welches Projekt gerade bearbeitet wird. Deckt nicht nur Aktoren ab, sondern
auch Sensoren, Wetterstationen, Bedienelemente usw. Jeder Eintrag hat:

- **Hersteller** (z.B. "MDT") und **Modell** (z.B. "AKS-2016.03")
- **Gruppe** — frei wählbar (Vorschläge: Aktor, Sensor, Wetterstation,
  Bedienelement, Sonstiges); bestimmt, wo das Gerät in der Liste erscheint
- **Beschreibung** — optionale Notiz
- **Type** und **Kanäle** — **nur bei der Gruppe "Aktor" relevant**: der
  Type muss dem Kanaltyp eines Punkttyps entsprechen (siehe Setup-Tab),
  damit das Gerät in der Abgangsliste zuordenbar ist. Bei anderen Gruppen
  bleiben diese Felder leer/ausgeblendet, und nur Aktoren erscheinen als
  Auswahl in der Abgangsliste.

Ein Suchfeld filtert live nach allen Feldern. Jeder Eintrag hat einen
**Bearbeiten**-Button, der ihn ins Formular oben lädt — Änderungen speichern
aktualisiert das bestehende Gerät statt ein neues anzulegen.
**⭳ Katalog exportieren (JSON)** / **⭱ Katalog importieren (JSON)** sichern
oder teilen den Katalog; der Import gleicht nach (Hersteller, Modell) ab —
dieselbe Datei mehrfach zu importieren ist unbedenklich.

Bei einer frischen Installation (leerer Katalog) wird beim ersten Start
automatisch ein Startkatalog gängiger KNX-Geräte eingefügt (u.a. MDT,
Busch-Jaeger, Theben, Elsner Elektronik, Gira, Phoenix Contact, Hörmann —
siehe `DEFAULT_ACTOR_TYPES` in `app/db.py`). Das passiert nur einmalig, wenn
die Tabelle leer ist — ein bereits befüllter oder bewusst geleerter Katalog
wird dadurch nie überschrieben.

### Setup

- **Kategorien** — die 6 Hauptgruppen, vorbelegt.
- **Punkttypen** — wiederverwendbare Definitionen wie "Licht (Dimmen)",
  "Rollo (einfach)", "Jalousie (mit Lamelle)", "Heizkreis", jeweils mit
  Datenpunkten, reserviertem Blockumfang und einem **Kanaltyp** (z.B.
  `Schalten`, `Dimmen`, `Rollo`, `Heizung`, `Tor`), der den Punkt mit
  passenden Aktortypen für die Abgangsliste verknüpft.
- **Zentral-/Allgemeinfunktions-Vorlagen** — automatisch erzeugte Blöcke:
  - `scope: building` → ein Block für das gesamte Projekt
  - `scope: floor` → ein Block je Geschoss (z.B. "Zentral EG", "Zentral OG")
  - `scope: room_multi` → ein Block **pro Raum**, nur für Räume mit einer
    Mindestanzahl an Punkten dieser Kategorie (Standard 2). Bei Rollo ist
    das bereits vorkonfiguriert: jeder Raum mit 2+ Jalousien erhält
    automatisch eine eigene "{Raum} Zentral Auf/Ab/Stop/Position" sowie
    eine einzelne "{Raum} Sperre"-Adresse für einen Langschläfer-Modus.
  - "Aussen-/unbeheizte Geschosse überspringen" (nur bei scope: floor) →
    schliesst als Aussen markierte Geschosse aus (z.B. macht eine
    "Fahrzeitmessung" je Geschoss für "Aussen" keinen Sinn)
  - Vorlagen der Kategorie Allgemein (Datum/Uhrzeit, Klima) werden jeweils
    zu einer eigenen Mittelgruppe, einmal je Projekt erzeugt.
- **Die Hauptgruppe einer Kategorie wird nur erzeugt, wenn sie im Projekt
  tatsächlich verwendet wird** — z.B. erscheint keine Hauptgruppe
  Steckdosen samt Zentralfunktion, wenn nie eine Steckdose hinzugefügt wird.

### Update

Prüft **nur auf Klick** — nichts läuft automatisch im Hintergrund.
**⟲ Nach Updates suchen** zeigt den aktuellen Stand und, falls auf GitHub
eine neuere Version vorliegt, einen **⭱ Update installieren**-Button.
Schlägt die Prüfung fehl, zeigt der Tab die tatsächliche Fehlermeldung an
statt kommentarlos "kein Update verfügbar" zu behaupten.

Voraussetzung, einmalig auf dem Server:
```bash
git branch --set-upstream-to=origin/main main
```
Das Repository ist öffentlich, daher funktioniert `git fetch`/`git pull`
anonym — es sind keine Git-Zugangsdaten im Container nötig.

So funktioniert es: `docker-compose.yml` bindet das **gesamte Repository**
in den Container ein. Ein `git pull` (ausgeführt vom Update-Button,
innerhalb des Containers gegen dasselbe eingebundene Verzeichnis)
aktualisiert den laufenden Code sofort — ein Neustart übernimmt ihn, ohne
dass ein Image-Rebuild nötig ist. Die Datenbank bleibt dabei unangetastet.
Ändern sich `requirements.txt` oder das `Dockerfile`, führt der Button
**keinen** automatischen Neustart durch — stattdessen zeigt er eine
Meldung, dass ein vollständiger Rebuild nötig ist (`docker compose up -d
--build`).

<details>
<summary>Falls das Repository später wieder privat wird</summary>

Dann braucht der Container Zugriff auf Ihre Git-Zugangsdaten, sonst
schlägt jede Prüfung mit einer Fehlermeldung wie `could not read
Username for 'https://github.com'` fehl. In `docker-compose.yml` sind
zwei Varianten als Kommentar vorbereitet — je nachdem, ob Sie HTTPS mit
Personal Access Token oder SSH verwenden, die passende Zeile
einkommentieren:

```yaml
# HTTPS mit Personal Access Token (im Credential Store des Hosts zwischengespeichert):
# - ~/.git-credentials:/root/.git-credentials:ro
# - ~/.gitconfig:/root/.gitconfig:ro

# SSH-Deploy-Key stattdessen:
# - ~/.ssh:/root/.ssh:ro
```

</details>

## PDF-Exporte

Alle drei PDF-Exporte (Abgangsliste, Geräteliste, Pflichtenheft) nutzen
dieselbe Gestaltung: ein dunkler Banner-Titelkopf, eine einheitliche
Tabellenoptik, und eine Fusszeile mit Projektname sowie **Seite X von Y**
auf jeder Seite. Der gemeinsame Code dafür liegt in `app/pdf_design.py`
(`pdf_styles()`, `pdf_title_banner()`, `pdf_table_style()`,
`make_numbered_canvas()`) — Änderungen dort wirken sich auf alle drei
Exporte gleichzeitig aus.

## Persistenz & Deployment

Projekte liegen in der SQLite-Datei `app/data/knx_ga.db`, die über
`docker-compose.yml` in den Container eingebunden wird — sie übersteht also
Container-Neubauten/-Neustarts, solange dieser Ordner nicht gelöscht wird.
Die JSON-Sicherung/-Wiederherstellung (siehe Gruppenadressen oben) ist für
explizite Portabilität gedacht, nicht für die normale Persistenz im Alltag
nötig. Für die Erstinstallation siehe *Schnellstart* oben.

### Update von einer früheren Version dieses Tools

Das Datenbankschema migriert beim Start automatisch (neue Spalten werden
ergänzt), eine bestehende `knx_ga.db` funktioniert also weiter. Die
*Vorbelegungsdaten* (Punkttypen, Zentralvorlagen, Standard-Gerätekatalog)
werden allerdings nur einmalig eingefügt, wenn die jeweilige Tabelle leer
ist — Korrekturen daran erscheinen also nicht rückwirkend in einer
bestehenden Installation. Solange sich noch keine echten Projektdaten
angesammelt haben, ist der einfachste Weg, `app/data/knx_ga.db` zu löschen
und neu vorbelegen zu lassen:

```bash
docker compose down
rm app/data/knx_ga.db
docker compose up -d --build
```

Bei bereits gespeicherten echten Projekten: zuerst mit dem
**⭳ Sichern (JSON)**-Button je Projekt sichern, dann die Datenbank löschen,
danach über **⭱ Aus Sicherung wiederherstellen** zurückspielen.

### Bereitstellung auf Proxmox

Ein schlankes LXC mit Docker ist die einfachste Variante:

1. Ein unprivilegiertes Debian/Ubuntu-LXC anlegen (1 vCPU / 512MB–1GB RAM
   reicht).
2. **Nesting** aktivieren (Optionen → Features), damit Docker im LXC
   laufen kann.
3. `apt update && apt install -y docker.io docker-compose-plugin` (falls
   dieses Paket auf Ihrer Distribution fehlt, alternativ die
   `docker-ce`-Pakete direkt von Docker installieren).
4. Dieses Verzeichnis (per `git clone`) hineinkopieren, hineinwechseln,
   `docker compose up -d --build`.
5. `http://<lxc-ip>:8000` aufrufen.

Das Dateisystem des LXC (inkl. der Datenbank) wird automatisch von den
üblichen Proxmox-Backup-Jobs erfasst.

## Hinweise / Einschränkungen

- Einzelbenutzer, keine Authentifizierung — nur im eigenen internen
  Netzwerk betreiben.
- Keine `.knxproj`-Manipulation — nur der offiziell unterstützte
  CSV-Importweg.
- Der ETS-Import überschreibt passende Einträge immer und löscht nie
  Einträge, die in der Datei fehlen — ein erneuter Export/Import räumt
  also keine Adressen auf, die im Tool zwischenzeitlich entfernt wurden;
  das bei Bedarf manuell in ETS erledigen.
- Reservierte `res`-Blöcke sind eine bewusste Übernahme Ihrer bestehenden
  Konvention (Zukunftssicherheit) — braucht ein Punkttyp (plus BWM, falls
  angehakt) irgendwann mehr Suffixe als sein Blockumfang, geht das Tool
  einfach über die Blockgrenze hinaus ohne aufzufüllen, wodurch
  nachfolgende Punkte sich verschieben. Blockgrössen grosszügig genug für
  die tatsächlich verwendeten Punkttypen wählen.
- Die Hauptgruppe einer Kategorie erscheint nur, wenn im Projekt
  tatsächlich etwas sie nutzt (ein Punkt oder eine Sonderadresse).
  Zentralvorlagen einer ungenutzten Kategorie werden ebenfalls nicht
  erzeugt.
- "Aussen-/unbeheizte Geschosse überspringen" gilt je Vorlage, nicht
  pauschal für alle — z.B. bezieht Beleuchtungs "Zentral {Geschoss}" ein
  Aussen-Geschoss weiterhin ein, solange dieses Häkchen nicht auch dort
  gesetzt wird.

## Code-Struktur

Das Backend ist modular aufgeteilt (statt einer einzigen grossen Datei):

```
app/
  main.py               — erstellt die App, bindet alle Router ein, mountet die Frontend-Dateien
  db.py                 — Datenbankverbindung, Schema, Migrationen, Standard-Vorbelegung
  models.py             — alle Pydantic-Schemas für Request-Bodies
  ga_logic.py            — Gruppenadressen-Baum-Generierung, Abgänge, Pflichtenheft-Hilfsfunktionen
  pdf_design.py          — gemeinsames PDF-Design (Banner, Tabellenstil, Seitenzahlen)
  utils.py               — kleine Hilfsfunktionen ohne eigene Abhängigkeiten
  routers/
    setup.py             — Kategorien, Punkttypen, Zentral-Vorlagen (Setup-Tab)
    geraete.py           — globaler Gerätekatalog (Geräte-Tab)
    projects.py          — Projekte (inkl. Metadaten), Geschosse/Räume/Punkte, Sicherung, GA-Export (Projekte-Tab)
    abgangsliste.py       — Aktoren, Abgänge, Kanalzuordnung, CSV/PDF-Export (Abgangsliste-Unterreiter)
    geraeteplanung.py     — Geräteplanung je Raum, Stückliste, PDF-Export (Geräteplanung-Unterreiter)
    pflichtenheft.py      — Pflichtenheft-PDF-Export (Pflichtenheft-Unterreiter)
    system.py             — Selbst-Update über Git (Update-Tab)
```

Diese Aufteilung folgt bewusst den Tabs der Oberfläche — wer eine Funktion
in der App sieht, findet den zugehörigen Code im gleichnamigen Modul. Für
Docker ändert sich dadurch nichts: `COPY app ./app` im Dockerfile und die
Repo-weite Einbindung in `docker-compose.yml` funktionieren beide rekursiv,
unabhängig von der internen Ordnerstruktur.

## Lizenz

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) — siehe
[`LICENSE`](./LICENSE). Bewusst gewählt, weil dies ein Netzwerkdienst ist
(eine Webanwendung): AGPL schliesst die "SaaS-Lücke", die die einfache GPL
hat — betreibt jemand eine geänderte Version dieses Tools als gehosteten
Dienst, muss der geänderte Quellcode auch dessen Nutzern zur Verfügung
gestellt werden, nicht nur jenen, denen eine Kopie ausgehändigt wird.

Vor einer Veröffentlichung "the project author(s)" im Lizenz-Header am
Anfang von `app/main.py` durch den tatsächlichen Namen bzw. die Firma
ersetzen.
