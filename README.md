# KNX Gruppenadressen-Generator (v2)

Direkt aus der Analyse echter ETS6-Exporte entwickelt. Ablauf:

**Geschosse → Räume → Punkte (Licht / Steckdosen / Fenster / Heizung) → fertig.**
Zentral- und Allgemeinfunktionen (Datum/Uhrzeit, Wetterstation, "alle Lichter
aus" je Geschoss usw.) werden automatisch aus Vorlagen erzeugt — normalerweise
muss man das pro Projekt gar nicht anfassen.

## Adressierungsmodell (entspricht Ihren echten Projekten)

| KNX-Ebene       | Zuordnung |
|-----------------|-----------|
| Hauptgruppe     | Funktionskategorie: `Allgemein, Beleuchtung, Steckdosen, Heizung, Rollo, Tore` |
| Mittelgruppe    | `Zentralfunktionen` + eine je Geschoss |
| Untergruppe     | Ein Adressblock je physischem Punkt: `{Raum} {Label} {Suffix}` |

Jeder Punkt reserviert einen **festen Adressblock** (Standard 5, oder 10 bei
Jalousien mit Lamelle) und füllt ungenutzte Plätze mit `res` für spätere
Erweiterungen auf — genau wie in Ihren bestehenden Projekten.

## CSV-Format — anhand Ihrer echten Exporte verifiziert

Tab-getrennt, jedes Feld in Anführungszeichen, mit Kopfzeile, Spalten:
```
Main  Middle  Sub  Address  Central  Unfiltered  Description  DatapointType  Security
```
DPTs werden als `DPST-x-y` geschrieben. `Security` ist immer `Auto`. Dies
wurde Byte für Byte gegen `Landes.csv`, `Steiner.csv` und `Mayrhofer.csv`
geprüft — alle drei verwenden ein identisches Format, daher sollte der
Import direkt über ETS6 funktionieren: Rechtsklick auf **Gruppenadressen**
→ **Gruppenadressen importieren**.

Falls sich Ihre Konventionen in ETS jemals ändern und Importe anfangen,
Zeilen zu überspringen: ein kleines Testprojekt exportieren und mit der
Ausgabe des Tools vergleichen — der CSV-Schreiber ist in `export_csv()`
in `app/main.py` isoliert.

## Verwendung

Das Tool hat vier Tabs:

- **Gruppenadressen** — Projekte aufbauen (Geschosse → Räume → Punkte),
  Vorschau ansehen und die ETS6-Gruppenadressen-CSV exportieren.
- **Abgangsliste** — Projekt wählen, die verbauten Aktoren anlegen und
  jeden Abgang einem Kanal zuordnen.
- **Aktoren** — der globale Aktor-Gerätekatalog (Hersteller / Modell /
  Type / Kanäle), gemeinsam für alle Projekte genutzt.
- **Setup** — Kategorien, Punkttypen und Zentral-/Allgemeinfunktions-
  Vorlagen. Wird im Alltag selten angefasst, ist bereits mit Ihren
  Konventionen vorbelegt.

### Setup-Tab

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
    automatisch eine eigene "{Raum} Zentral Auf/Ab/Stop/Position" (auf
    einen Blockumfang wie 5 aufgefüllt) sowie eine einzelne "{Raum} Sperre"-
    Adresse für einen Langschläfer-Modus — rein abhängig davon, wie viele
    Jalousien Sie diesem Raum hinzufügen, ohne manuellen Aufwand.
  - "Aussen-/unbeheizte Geschosse überspringen" (nur bei scope: floor) →
    schliesst als Aussen markierte Geschosse aus (z.B. macht eine
    "Fahrzeitmessung" oder ein "Sommer/Winter Status" je Geschoss für
    "Aussen" keinen Sinn)
  - Vorlagen der Kategorie Allgemein (Datum/Uhrzeit, Klima) werden jeweils
    zu einer eigenen Mittelgruppe, unabhängig von der Geschossanzahl
    einmal je Projekt erzeugt.
- **Die Hauptgruppe einer Kategorie wird nur erzeugt, wenn sie im Projekt
  tatsächlich verwendet wird** — z.B. erscheint keine Hauptgruppe
  Steckdosen samt Zentralfunktion, wenn nie eine Steckdose hinzugefügt wird.

### Gruppenadressen-Tab

- Projekt anlegen, Geschosse (Stockwerke) hinzufügen. Ein Geschoss als
  **Aussen/unbeheizt** markieren (z.B. "Aussen", "Garage"), wenn es von
  entsprechend markierten Vorlagen ausgeschlossen werden soll.
- Räume je Geschoss hinzufügen.
- Für jeden Raum Punkte hinzufügen: Punkttyp wählen (z.B. "Licht
  (Dimmen)"), ein Label vergeben (z.B. "Spots", "Decke", "Nord" für ein
  Fenster), bei Bedarf eine Anzahl für mehrere gleiche auf einmal, und
  **+BWM** ankreuzen, falls dieser Punkt eine Bewegungsmelder-Adresse
  braucht.
- **Alles Spezielle** (eine Einzel-Szene, eine spezielle Zentralgruppe für
  einen bestimmten Raum wie "Kind1 Zentral") kommt unter **Sonder-/
  Zusatzadressen** — Kategorie wählen, festlegen ob es zu
  `Zentralfunktionen` oder einem bestimmten Geschoss gehört, benennen und
  die Datenpunkte angeben.
- **Vorschau** zur Kontrolle, dann **CSV für ETS6 herunterladen**.
- **⭳ Sichern (JSON)** speichert die komplette Projektdefinition
  (Geschosse, Räume, Punkte, Sonderadressen) als `.json`-Datei — getrennt
  von der ETS-CSV, gedacht zum Sichern / Duplizieren / Umziehen eines
  Projekts zwischen Installationen. **⭱ Aus Sicherung wiederherstellen**
  in der Projektliste erstellt ein Projekt aus dieser Datei neu. Punkttypen/
  Kategorien werden dabei per Name mit der Zielinstallation abgeglichen;
  was nicht übereinstimmt, wird übersprungen und gemeldet, nie einfach
  angenommen. Existiert bereits ein Projekt mit gleichem Namen, wird der
  Import als "<Name> (imported)" gespeichert statt es zu überschreiben.
- **× Schliessen** klappt die geöffnete Projektansicht ein, ohne etwas zu
  löschen — praktisch, sobald mehrere Projekte angelegt sind und die
  Seite lang wird.

### Aktoren-Tab

Ihr Aktor-Gerätekatalog — **global, gemeinsam für alle Projekte**
(dieselbe Liste, unabhängig davon welches Projekt gerade verdrahtet wird).
Jeder Eintrag hat:

- **Hersteller** (z.B. "MDT")
- **Modell** (z.B. "AKS-2016.03")
- **Type** — muss dem Kanaltyp eines Punkttyps entsprechen (`Schalten`,
  `Dimmen`, `Rollo`, `Heizung`, `Tor`, oder ein selbst angelegter), um
  diesem zuordenbar zu sein
- **Kanäle** — wie viele physische Ausgänge das Gerät hat

**⭳ Katalog exportieren (JSON)** / **⭱ Katalog importieren (JSON)** zum
Sichern oder Teilen dieses Katalogs. Der Import gleicht nach (Hersteller,
Modell) ab: existiert diese Kombination schon, werden Type/Kanalzahl
aktualisiert, sonst wird ein neuer Eintrag angelegt — dieselbe Datei
mehrfach zu importieren ist unbedenklich.

### Wo Projekte tatsächlich gespeichert werden

Projekte liegen in der SQLite-Datei `app/data/knx_ga.db`, die über
`docker-compose.yml` in den Container eingebunden wird — sie übersteht
also Container-Neubauten/-Neustarts, solange dieser Ordner nicht gelöscht
wird. Die JSON-Sicherung/-Wiederherstellung oben ist für explizite
Portabilität gedacht (ein Projekt auf eine andere Maschine bringen, eine
externe Kopie behalten), nicht für die normale Persistenz im Alltag nötig.

### Abgangsliste (Aktoren-Verdrahtung / Kanalliste)

Sobald ein Projekt Räume und Punkte enthält, kennt das Tool bereits jeden
physischen Ausgang, der benötigt wird (jeder Schalt-, Dimm-, Jalousie- und
Heizkanal). Der **Abgangsliste**-Tab macht daraus eine Verdrahtungsliste
für den Elektriker:

1. **Setup → Punkttypen**: jeder Punkttyp hat einen **Kanaltyp** (z.B.
   `Schalten`, `Dimmen`, `Rollo`, `Heizung`, `Tor`) und **benötigte
   Kanäle** (meist 1). Für alle mitgelieferten Punkttypen bereits ausgefüllt.
2. **Aktoren-Tab**: den Aktor-Gerätekatalog anlegen — z.B. Hersteller
   "MDT", Modell "AKS-2016.03", Type `Schalten`, 20 Kanäle. Der Type muss
   dem Kanaltyp eines Punkttyps entsprechen, um zuordenbar zu sein. Dieser
   Katalog ist global und gilt für alle Projekte.
3. **Abgangsliste-Tab**: Projekt aus der Liste wählen, dann die
   tatsächlich verbauten **Aktoren** hinzufügen (Aktortyp wählen, in
   welchem Geschoss/welcher UV er sitzt, Standortbezeichnung, physische
   KNX-Adresse wie `1.1.2`).
4. Jeder **Abgang** (eine Zeile je benötigtem physischen Ausgang) erscheint
   darunter mit einer Auswahl aller Kanäle passender Aktoren. Einen manuell
   wählen, oder **Alle automatisch zuordnen** klicken, um jeden noch nicht
   zugeordneten Abgang automatisch dem ersten freien passenden Kanal
   zuzuweisen (in Geschoss-/Raum-Reihenfolge).
5. **Abgangsliste herunterladen (CSV)** exportiert eine Tabelle mit den
   Spalten `Geschoss, Raum/UV, Aktor, Physikalische Adr., Kanal, Funktion`
   — jeder Kanal jedes Aktors wird aufgeführt, unbelegte mit `RESERVE`
   markiert, im Layout einer handgemachten Verdrahtungsliste.

Dies ist ein eigener Export, getrennt von der ETS-Gruppenadressen-CSV —
der eine dient der Busprogrammierung, der andere der Schaltschrank-
Verdrahtung.

### Hinweis zu Kundendokumentations-Exporten

Ein kundenseitiger Dokumentations-Export (schöneres Format, Beschreibungen
usw.) wurde als mögliche zukünftige Erweiterung erwähnt — der aktuelle
CSV-Export ist auf den ETS-Import ausgerichtet, nicht dafür gedacht. Das
wäre ein naheliegender nächster Schritt (z.B. eine formatierte Word/PDF-
oder Markdown-Tabelle je Raum, auf denselben Daten von `build_ga_tree()`
aufbauend, die auch die CSV nutzt) — jederzeit gerne umsetzbar.

## Selbst-Update über Git

Der Header oben in der App zeigt den aktuellen Stand und, falls auf
GitHub eine neuere Version vorliegt, einen **⭱ Aktualisieren**-Button.

So funktioniert es: `docker-compose.yml` bindet das **gesamte Repository**
in den Container unter `/app` ein. Ein `git pull` (ausgeführt vom
Aktualisieren-Button, innerhalb des Containers gegen dasselbe
eingebundene Verzeichnis) aktualisiert den laufenden Code sofort — ein
Neustart übernimmt ihn, ohne dass ein Image-Rebuild nötig ist. Die
Datenbank liegt unter `app/data/knx_ga.db`, also innerhalb derselben
Einbindung, und bleibt beim Update unangetastet.

**Wichtige Einschränkung:** ändern sich `requirements.txt` oder das
`Dockerfile`, führt der Button **keinen** automatischen Neustart durch
(neue Abhängigkeiten wären ja noch nicht installiert) — stattdessen zeigt
er eine Meldung, dass ein vollständiger Rebuild nötig ist:
```bash
docker compose up -d --build
```

**Voraussetzung für ein privates GitHub-Repository:** damit `git pull`
innerhalb des Containers funktioniert, braucht der Container Zugriff auf
Ihre Git-Zugangsdaten. In `docker-compose.yml` sind zwei Varianten als
Kommentar vorbereitet — je nachdem, ob Sie HTTPS mit Personal Access
Token oder SSH verwenden, die passende Zeile einkommentieren:
```yaml
# HTTPS mit Personal Access Token (im Credential Store des Hosts zwischengespeichert):
# - ~/.git-credentials:/root/.git-credentials:ro
# - ~/.gitconfig:/root/.gitconfig:ro

# SSH-Deploy-Key stattdessen:
# - ~/.ssh:/root/.ssh:ro
```

Damit der Update-Status korrekt erkannt wird, muss der Branch einen
Tracking-Branch gesetzt haben (einmalig auf dem Server):
```bash
git branch --set-upstream-to=origin/main main
```

## Mit Docker starten

```bash
docker compose up -d --build
```
`http://<host>:8000` öffnen. Daten bleiben in `app/data/knx_ga.db`
(über die Repository-Einbindung) erhalten.

## Update von einer früheren Version dieses Tools

Das Datenbankschema migriert beim Start automatisch (neue Spalten werden
ergänzt), eine bestehende `knx_ga.db` funktioniert also weiter. Die
*Vorbelegungsdaten* (Punkttypen, Zentralvorlagen) werden allerdings nur
einmalig eingefügt, wenn die Kategorien-Tabelle leer ist — Namenskorrekturen
wie "Schalten Status" oder die überarbeiteten Sommer/Winter-Vorlagen
erscheinen also nicht rückwirkend in einer bestehenden Installation.
Solange sich hier noch keine echten Projektdaten angesammelt haben, ist
der einfachste Weg, `app/data/knx_ga.db` zu löschen und neu vorbelegen zu
lassen:

```bash
docker compose down
rm app/data/knx_ga.db
docker compose up -d --build
```

Bei bereits gespeicherten echten Projekten: zuerst mit dem
**⭳ Sichern (JSON)**-Button je Projekt sichern, dann die Datenbank
löschen, danach über **⭱ Aus Sicherung wiederherstellen** zurückspielen.

## Bereitstellung auf Proxmox

Wie bisher — ein schlankes LXC mit Docker ist die einfachste Variante:

1. Ein unprivilegiertes Debian/Ubuntu-LXC anlegen (1 vCPU / 512MB–1GB RAM
   reicht).
2. **Nesting** aktivieren (Optionen → Features), damit Docker im LXC
   laufen kann.
3. `apt update && apt install -y docker.io docker-compose-plugin`
   (oder die `docker-ce`-Pakete von Docker direkt, siehe frühere
   Chat-Historie bei Problemen mit `docker-compose-plugin`).
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
  pauschal für alle — z.B. bezieht Beleuchtungs "Zentral {Geschoss}"
  ein Aussen-Geschoss weiterhin ein, solange dieses Häkchen nicht auch
  dort gesetzt wird.

## Lizenz

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) —
siehe [`LICENSE`](./LICENSE). Bewusst gewählt, weil dies ein Netzwerkdienst
ist (eine Webanwendung): AGPL schliesst die "SaaS-Lücke", die die einfache
GPL hat — betreibt jemand eine geänderte Version dieses Tools als
gehosteten Dienst, muss der geänderte Quellcode auch dessen Nutzern zur
Verfügung gestellt werden, nicht nur jenen, denen eine Kopie ausgehändigt
wird.

Vor einer Veröffentlichung "the project author(s)" im Lizenz-Header am
Anfang von `app/main.py` durch den tatsächlichen Namen bzw. die Firma
ersetzen.
