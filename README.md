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
docker compose pull
docker compose up -d
```

Danach `http://<host>` öffnen (läuft auf Port 80, kein `:8000` nötig).

**Beim ersten Start:**
- Kategorien, Funktionstypen und Zentral-/Allgemeinfunktions-Vorlagen sind
  bereits mit sinnvollen Standardwerten vorbelegt (siehe Setup-Tab unten).
- Der Geräte-Katalog-Tab wird automatisch mit einem Startkatalog gängiger
  KNX-Geräte gefüllt (siehe Geräte-Katalog-Tab unten).
- Es gibt **keine Benutzerauthentifizierung** — nur im eigenen internen
  Netzwerk betreiben, nie direkt ans Internet exponieren.

Für eine Proxmox/LXC-Bereitstellung und weitere Deployment-Details siehe
[`DEPLOYMENT.md`](./DEPLOYMENT.md); für spätere Updates den **Update**-Tab
in der App verwenden (siehe unten) oder manuell `git pull` + Neustart.

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
in `backend/routers/projects.py` isoliert.

## Die vier Tabs

- **Projekte** — Projekte anlegen/suchen/öffnen; ein Klick auf den kleinen
  Pfeil ▾ daneben öffnet ein Menü mit **Neues Projekt** und
  **Projekt öffnen** als Abkürzung von überall in der App aus. Ein
  geöffnetes Projekt zeigt einen Arbeitsbereich mit acht Unterreitern
  (Übersicht, Gebäudestruktur, Funktionen, Gruppenadressen, Abgangsliste,
  Geräteplanung, Pflichtenheft, Klärungsliste), die alle am selben Projekt
  arbeiten.
- **Geräte Katalog** — globaler Gerätekatalog (Aktoren, Sensoren,
  Bedienelemente usw.), gemeinsam für alle Projekte genutzt.
- **Setup** — Firmenprofil (Name/Adresse/Kontakt/Logo), Kategorien,
  Funktionstypen und Zentral-/Allgemeinfunktions-Vorlagen als eigene
  Unterreiter. Funktionstypen und Vorlagen lassen sich nachträglich
  bearbeiten (nicht nur löschen/neu anlegen); Kategorien lassen sich
  umbenennen, aber nicht neu anordnen/hinzufügen/löschen, da ihre
  Reihenfolge direkt den festen KNX-Hauptgruppennummern entspricht.
- **Update** — prüft auf Wunsch, ob auf GitHub eine neuere Version vorliegt,
  installiert sie, und zeigt das Änderungsprotokoll dieses Tools an.

### Projekte

**Projektliste** (Standardansicht): ein Suchfeld filtert live nach Name,
Kunde, Standort, Status und Bestellnummer, die als Badges neben jedem
Projektnamen erscheinen. **+ Neues Projekt** öffnet ein Formular (Name,
Kunde, Standort, Status, Bestellnummer, Kommentar — alle Felder ausser
Name optional) und wechselt nach dem Anlegen direkt in den Arbeitsbereich
des neuen Projekts. **⭱ Aus Sicherung wiederherstellen (JSON)** legt aus
einer zuvor exportierten Datei ein neues Projekt an (siehe Gruppenadressen
unten) — existiert bereits ein Projekt mit gleichem Namen, wird der Import
als "<Name> (imported)" gespeichert statt es zu überschreiben.

**Öffnen** eines Projekts zeigt dessen Arbeitsbereich (die Projektliste
wird dabei ausgeblendet, nicht darunter weiter angezeigt): oben die
Projekt-Metadaten mit **Bearbeiten**-Button (ändert Name/Kunde/Standort/
Status/Bestellnummer/Kommentar nachträglich), daneben **⭳ Sichern (JSON)**
und **× Schliessen**. **× Schliessen** kehrt zur Projektliste zurück, ohne
etwas zu löschen — beim nächsten Öffnen startet der Arbeitsbereich wieder
beim Unterreiter Übersicht, der auf einen Blick zeigt, wie weit jeder der
übrigen sieben Unterreiter gediehen ist (mit direktem Sprung dorthin per
Klick).

#### Gebäudestruktur

Nur das Gebäude selbst — welche Funktionen wo landen, ist Sache des
Unterreiters Funktionen weiter unten.

- Geschosse (Stockwerke) hinzufügen; ein Geschoss als **Aussen/unbeheizt**
  markieren (z.B. "Aussen", "Garage"), wenn es von entsprechend markierten
  Vorlagen ausgeschlossen werden soll.
- Räume je Geschoss hinzufügen — einzeln, oder über **Mehrere...** eine
  Liste von Raumnamen (ein Name pro Zeile) auf einmal einfügen.
- Sowohl Geschoss- als auch Raumnamen lassen sich über den
  **Bearbeiten**-Button daneben jederzeit nachträglich umbenennen.

#### Funktionen

- Jedem im Unterreiter Gebäudestruktur angelegten Raum Punkte zuweisen:
  Funktionstyp wählen (z.B. "Licht (Dimmen)"), ein Label vergeben (z.B.
  "Spots", "Decke", "Nord" für ein Fenster), bei Bedarf eine Anzahl für
  mehrere gleiche auf einmal, und **+BWM** ankreuzen, falls dieser Punkt
  eine Bewegungsmelder-Adresse braucht. Über das ✎-Symbol an jedem bereits
  zugewiesenen Punkt lässt sich Funktionstyp/Label/BWM nachträglich ändern,
  ohne ihn löschen und neu anlegen zu müssen.
- **Alles Spezielle** (Einzel-Szene, spezielle Zentralgruppe für einen
  bestimmten Raum wie "Kind1 Zentral") kommt unter **Sonder-/
  Zusatzadressen** — Kategorie wählen, festlegen ob es zu
  `Zentralfunktionen` oder einem bestimmten Geschoss gehört, benennen und
  die Datenpunkte angeben.

#### Gruppenadressen

- Beim Öffnen des Unterreiters erscheinen die aus Gebäudestruktur und
  Funktionen erzeugten Gruppenadressen sofort als aufklappbarer Baum
  (Hauptgruppe → Mittelgruppe → Adresse) — **Vorschau** lädt ihn bei
  Bedarf manuell neu, **Alle aufklappen**/**Alle einklappen** klappen ihn
  komplett auf bzw. zu.
- **CSV für ETS6 herunterladen** exportiert dieselben Adressen als
  ETS6-kompatible CSV-Datei.
- **⭳ Sichern (JSON)** (im Projektkopf oben, unterreiterübergreifend
  sichtbar) speichert die komplette Projektdefinition (Metadaten,
  Geschosse, Räume, Punkte, Sonderadressen) als `.json`-Datei — getrennt
  von der ETS-CSV, gedacht zum Sichern / Duplizieren / Umziehen eines
  Projekts zwischen Installationen. Beim Wiederherstellen werden
  Funktionstypen/Kategorien per Name mit der Zielinstallation abgeglichen; was
  nicht übereinstimmt, wird übersprungen und gemeldet, nie einfach
  angenommen.

#### Abgangsliste

Sobald ein Projekt Räume und Punkte enthält, kennt das Tool bereits jeden
physischen Ausgang, der benötigt wird (jeder Schalt-, Dimm-, LED-, Jalousie-
und Heizkanal). Dieser Unterreiter macht daraus eine Verdrahtungsliste für
den Elektriker — getrennt von der ETS-Gruppenadressen-CSV: die eine dient
der Busprogrammierung, die andere der Schaltschrank-Verdrahtung.

1. Jeder Funktionstyp hat einen **Kanaltyp** (z.B. `Schalten`, `Dimmen`, `LED`,
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

#### Klärungsliste

Interne Arbeitsliste für Fragen, Aufgaben und Notizen, die z.B. bei einem
Kundentermin anfallen (etwa "Tasterfarbe schwarz oder weiss?") — erscheint
**nicht** im Pflichtenheft-Export, rein zur eigenen Nachverfolgung.

- Jeder Eintrag hat einen **Typ** (Frage / Aufgabe / Notiz) und optional
  einen **Raum**, darin wiederum optional einen bestimmten **Punkt**; ohne
  Raum landet er unter "Allgemein". Die Liste ist nach Raum gruppiert.
- **Status** (offen / geklärt / abgelehnt) wird über Schnellaktions-Buttons
  direkt in der Liste gesetzt, ohne ein Formular zu öffnen.
- **Antwort/Ergebnis** ist direkt in jedem Eintrag editierbar und speichert
  beim Verlassen des Felds — gedacht für den Ablauf "erst alle Fragen
  anlegen, dann beim Termin der Reihe nach beantworten und auf Geklärt
  setzen", ohne für jede Antwort ins Bearbeiten-Formular wechseln zu müssen.
- **Bearbeiten** im oberen Formular ändert nur die strukturellen Felder
  (Typ/Raum/Punkt/Text) — die bereits erfasste Antwort bleibt dabei
  erhalten.
- Der Unterreiter-Button zeigt die Anzahl noch offener Einträge an
  (z.B. "Klärungsliste (3)"), sobald ein Projekt geöffnet ist.

### Geräte Katalog

Globaler Gerätekatalog — **gemeinsam für alle Projekte**, unabhängig davon
welches Projekt gerade bearbeitet wird. Deckt nicht nur Aktoren ab, sondern
auch Sensoren, Wetterstationen, Bedienelemente usw. Jeder Eintrag hat:

- **Hersteller** (z.B. "MDT") und **Modell** (z.B. "AKS-2016.03")
- **Gruppe** — frei wählbar (Vorschläge: Aktor, Sensor, Wetterstation,
  Bedienelement, Sonstiges); bestimmt, wo das Gerät in der Liste erscheint
- **Beschreibung** — optionale Notiz
- **Type** und **Kanäle** — **nur bei der Gruppe "Aktor" relevant**: der
  Type muss dem Kanaltyp eines Funktionstyps entsprechen (siehe Setup-Tab),
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
siehe `DEFAULT_ACTOR_TYPES` in `backend/db.py`). Das passiert nur einmalig, wenn
die Tabelle leer ist — ein bereits befüllter oder bewusst geleerter Katalog
wird dadurch nie überschrieben.

### Setup

Firma, Kategorien, Funktionstypen und Zentral-/Allgemeinfunktions-Vorlagen sind
eigene Unterreiter innerhalb des Setup-Tabs, nicht alle gleichzeitig
sichtbar.

- **Firma** — Name, Adresse, Telefon, E-Mail, Website und ein Logo,
  einmalig hinterlegt. Erscheint als Badge im Programmkopf neben dem
  KNXpilot-Logo (Logo + Name), sobald etwas hinterlegt ist. Zusätzlich
  gibt es einen globalen Schalter **"Firmenlogo/-daten auf
  PDF-Exporten anzeigen"** — gilt für alle drei PDF-Exporte
  gleichzeitig, kein Umschalten je Export nötig (siehe *PDF-Exporte*
  weiter unten). Das Logo wird beim Hochladen
  automatisch auf den sichtbaren Bildinhalt zugeschnitten (entfernt
  transparente/weisse Rahmen um das eigentliche Motiv), damit es in
  der kleinen Kopfzeilen-Badge nicht winzig wirkt.
- **Kategorien** — die 6 Hauptgruppen, vorbelegt; der Name jeder Kategorie
  lässt sich über **Bearbeiten** umbenennen, Reihenfolge (=
  Hauptgruppennummer) und Anzahl bleiben fest.
- **Funktionstypen** — wiederverwendbare Definitionen wie "Licht (Dimmen)",
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
statt kommentarlos "kein Update verfügbar" zu behaupten. Voraussetzungen
auf dem Server und wie der Mechanismus intern funktioniert (git pull +
Neustart, kein Image-Rebuild) siehe [`DEPLOYMENT.md`](./DEPLOYMENT.md).

Darunter zeigt der Tab das **Änderungsprotokoll** dieses Tools
(`CHANGELOG.md`), damit ersichtlich ist, was sich seit der letzten
Installation geändert hat, ohne extra auf GitHub nachsehen zu müssen.

## PDF-Exporte

Alle drei PDF-Exporte (Abgangsliste, Geräteliste, Pflichtenheft) nutzen
dieselbe Gestaltung: ein dunkler Banner-Titelkopf, eine einheitliche
Tabellenoptik, und eine Fusszeile mit Projektname sowie **Seite X von Y**
auf jeder Seite. Der gemeinsame Code dafür liegt in `backend/pdf_design.py`
(`pdf_styles()`, `pdf_title_banner()`, `pdf_table_style()`,
`make_numbered_canvas()`) — Änderungen dort wirken sich auf alle drei
Exporte gleichzeitig aus.

Ist im Setup-Tab unter *Firma* der Schalter "Firmenlogo/-daten auf
PDF-Exporten anzeigen" aktiv, ergänzt `company_header_block()` oben auf
Seite 1 Firmenname und Logo (neben dem Titel-Banner), während
`company_footer_line()` Adresse, Telefon, E-Mail und Website als
eigene, zentrierte Zeile unterhalb von "Seite X von Y" auf **jeder**
Seite einfügt. Ist der Schalter aus oder kein Firmenprofil hinterlegt,
liefern beide Funktionen einfach nichts zurück — die Aufrufer in den
drei Router-Dateien brauchen dafür kein `if`.

## Persistenz & Deployment

Für Details zu Datenpersistenz, Update-Mechanismus und
Proxmox/LXC-Bereitstellung siehe [`DEPLOYMENT.md`](./DEPLOYMENT.md).

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
  Konvention (Zukunftssicherheit) — braucht ein Funktionstyp (plus BWM, falls
  angehakt) irgendwann mehr Suffixe als sein Blockumfang, geht das Tool
  einfach über die Blockgrenze hinaus ohne aufzufüllen, wodurch
  nachfolgende Punkte sich verschieben. Blockgrössen grosszügig genug für
  die tatsächlich verwendeten Funktionstypen wählen.
- Die Hauptgruppe einer Kategorie erscheint nur, wenn im Projekt
  tatsächlich etwas sie nutzt (ein Punkt oder eine Sonderadresse).
  Zentralvorlagen einer ungenutzten Kategorie werden ebenfalls nicht
  erzeugt.
- "Aussen-/unbeheizte Geschosse überspringen" gilt je Vorlage, nicht
  pauschal für alle — z.B. bezieht Beleuchtungs "Zentral {Geschoss}" ein
  Aussen-Geschoss weiterhin ein, solange dieses Häkchen nicht auch dort
  gesetzt wird.

## Code-Struktur

Backend (FastAPI) und Frontend (vanilla HTML/CSS/JS, kein Build-Schritt)
liegen in getrennten Verzeichnissen — Details, wie man lokal entwickelt und
wo welcher Code liegt, siehe [`DEVELOPMENT.md`](./DEVELOPMENT.md).

## Lizenz

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) — siehe
[`LICENSE`](./LICENSE). Bewusst gewählt, weil dies ein Netzwerkdienst ist
(eine Webanwendung): AGPL schliesst die "SaaS-Lücke", die die einfache GPL
hat — betreibt jemand eine geänderte Version dieses Tools als gehosteten
Dienst, muss der geänderte Quellcode auch dessen Nutzern zur Verfügung
gestellt werden, nicht nur jenen, denen eine Kopie ausgehändigt wird.

Vor einer Veröffentlichung "the project author(s)" im Lizenz-Header am
Anfang von `backend/main.py` durch den tatsächlichen Namen bzw. die Firma
ersetzen.
