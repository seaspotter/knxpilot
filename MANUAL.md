# KNXpilot – Bedienungsanleitung

Auch direkt in der App verfügbar (Tab **Hilfe**), identisch gerendert.

## Adressierungsmodell

- **Hauptgruppe** → Funktionskategorie: `Allgemein, Beleuchtung,
  Steckdosen, Heizung, Rollo, Tore`
- **Mittelgruppe** → `Zentralfunktionen` + eine je Geschoss
- **Untergruppe** → ein Adressblock je physischem Punkt:
  `{Raum} {Label} {Suffix}`

Jeder Punkt reserviert einen festen Adressblock (Standard 5, bei Jalousien
mit Lamelle 10) und füllt ungenutzte Plätze mit `res` für spätere
Erweiterungen auf.

Kategorien lassen sich umbenennen (Setup → Kategorien), aber nicht
umsortieren oder neue hinzufügen — die Reihenfolge entspricht fest den
KNX-Hauptgruppennummern (0–31 möglich, Mittelgruppen nur 0–7), ein anderes
Schema (z.B. Geschoss als Hauptgruppe) würde diesen Rahmen sprengen.

## GA-CSV-Format für ETS6

Tab-getrennt, in Anführungszeichen, mit Kopfzeile:
```
Main  Middle  Sub  Address  Central  Unfiltered  Description  DatapointType  Security
```
DPTs als `DPST-x-y`, `Security` immer `Auto`. Import: Rechtsklick auf
**Gruppenadressen** → **Gruppenadressen importieren**.

## Die Tabs

- **Projekte** — anlegen/suchen/öffnen; ein geöffnetes Projekt hat einen
  Arbeitsbereich mit vierzehn Unterreitern (Details unten).
- **Geräte Katalog** — globaler Gerätekatalog, gemeinsam für alle Projekte.
- **Zeiterfassung** — Arbeitszeit je Projekt, abschaltbar unter
  Setup → Zeiterfassung.
- **Setup** — Firmenprofil, Kategorien, Funktionstypen,
  Zentral-/Allgemeinfunktions-Vorlagen, Pflichtenheft/Dokumentation-Inhalt,
  E-Mail, Backup, Zeiterfassung (Details unten).
- **Update** — prüft auf Klick auf eine neue Version, zeigt das
  Änderungsprotokoll.
- **Hilfe** — diese Anleitung, mit Inhaltsverzeichnis und Suche.

### Projekte

**Projektübersicht** (über der Liste): drei Karten — **Projekte gesamt**
(je Status, klickbar), **Offene Klärungen** (inkl. seit >7 Tagen
unbeantwortet, klickbar zur Klärungsliste), **Ohne Struktur** (Projekte
ohne Geschoss, klickbar zur Gebäudestruktur).

**Projektliste**: Suchfeld filtert nach Name/Kunde/Standort/Status/
Bestellnummer. **+ Neues Projekt** legt an und öffnet direkt. **⭱** oben
stellt aus einer JSON-Sicherung wieder her (Namenskonflikt → "<Name>
(imported)"). Jede Zeile: **Öffnen**, **Duplizieren** (sofortige Kopie
"<Name> (Kopie)"), **Löschen**.

**Öffnen** zeigt den Arbeitsbereich: Metadaten mit **Bearbeiten**
(inkl. **E-Mail**/**Weitere Empfänger** für den PDF-Versand), **⭳** (JSON
sichern), **⧉** (duplizieren), **× Schliessen**. Eine Marke 📁 im
Programmkopf zeigt das offene Projekt von überall — Klick springt hin, ×
daneben schliesst. Start ist immer der Unterreiter Übersicht (Fortschritt
je Unterreiter, klickbar).

**Dateien**: eigene Referenzdateien hochladen (Baupläne usw., max. 25 MB).
Teil von Datenbank- und JSON-Sicherung, nicht von Duplizieren. Für
Gerätehandbücher gibt es den eigenen Unterreiter Handbücher.

#### Gebäudestruktur

Nur das Gebäude selbst — Funktionen kommen im Unterreiter Funktionen.

Baum wie in ETS: Geschoss → Raum → Verteiler, jedes Geschoss auf-/zuklappbar.

- Geschosse anlegen, optional als **Aussen/unbeheizt** markieren.
- Räume anlegen (**+ Raum**, oder **Mehrere...** für eine Liste auf einmal).
- **✎** benennt um, **×** löscht.
- **Ziehen und Ablegen** verschiebt Räume/Geschosse/Verteiler (nimmt
  Funktionen/Geräte/Klärungen mit); **⇄** macht dasselbe ohne Maus.
- Verschieben ändert meist Gruppenadressen (Mittelgruppe = Geschoss) —
  KNXpilot fragt vorher nach; "Änderungen seit dem letzten ETS-Export"
  (Gruppenadressen) zeigt danach, was in ETS nachzuziehen ist.
- **Löschen** listet immer genau auf, was mitgelöscht wird.
- **KNX-Linien (optional)**: nur bei mehreren TP-Linien nötig (Linienkoppler).
  Bereich/Linie/Name eintragen, dann je Geschoss/Raum/Aktor zuweisbar. Ohne
  Zuweisung gilt die erste (**Standard**) Linie. Zeigt je Linie Geräteanzahl
  und Warnungen (>64 Geräte, fehlender Koppler/Spannungsversorgung).

#### Funktionen

- Je Raum Punkte zuweisen: Funktionstyp, Label (z.B. "Spots"), optional
  Anzahl und **+BWM**. **✎** ändert nachträglich.
- Sonderfälle (Einzel-Szene, raumspezifische Zentralgruppe) unter
  **Sonder-/Zusatzadressen**.

#### Gruppenadressen

- Baum (Hauptgruppe → Mittelgruppe → Adresse), immer frisch erzeugt.
- **CSV für ETS6 herunterladen** exportiert sie.
- **Änderungen seit dem letzten ETS-Export**: seit dem letzten CSV-Download
  neu/verschoben/geändert/entfernt, in Abarbeitungsreihenfolge. **Aktuellen
  Stand als übernommen markieren** setzt den Stand ohne Download.
- **⭳** (Programmkopf) sichert das komplette Projekt als JSON (alles ausser
  Zeiterfassung) — zum Wiederherstellen/Umziehen. **Duplizieren** (⧉) ist
  die schnelle Kopie für dieselbe Installation: nur die Planung, ohne
  Klärungen/Checklisten-Haken/Unterschriften/Dateien/Handbücher.

#### Abgangsliste

Verdrahtungsliste für den Elektriker (getrennt von der ETS-CSV).

1. Jeder Funktionstyp hat einen **Kanaltyp** und benötigte Kanäle.
2. Aktoren im Geräte-Katalog anlegen (**Type** passend zum Kanaltyp).
3. **Bedarfsübersicht** zeigt benötigte/zugeordnete/offene Kanäle je
   Geschoss und Kanaltyp.
4. Aktoren hinzufügen (Typ, Geschoss/UV, Standort, physische Adresse).
   **Bearbeiten** ändert Geschoss/Standort/Adresse nachträglich.
5. Jeder **Abgang** wählt einen Kanal — manuell, oder **Alle automatisch
   zuordnen** (mischt nie Geschosse, bevorzugt bei Rollo/Jalousie
   ausgerichtete Kanalpaare). Vorschau vor dem Speichern.
6. **CSV/PDF herunterladen** exportieren die Verdrahtungsliste
   (unbelegte Kanäle als `RESERVE`).
7. **PA automatisch zuordnen** (auch in Geräteplanung, wirkt auf beide)
   vergibt physische Adressen für alle Geräte ohne eine — feste
   Reihenfolge (Systemgeräte, dann je Geschoss Aktoren, dann Sensoren/
   Bedienelemente, dann Aussen), in Zehnerblöcken je Bedarf. Bestehende
   Adressen bleiben unverändert. Bei KNX-Linien wird jede Linie einzeln
   nummeriert.

#### Labels

Etikettenbogen für die Schaltschrankbeschriftung — ein Etikett je Gerät mit
physischer Adresse (Aktoren + Geräteplanung), sortiert nach Adresse, zweite
Zeile nur der Ort (kein Gerätetyp).

- **Format**: aktuell nur Avery Zweckform L6037 (189/Bogen).
- **Startposition**: Klick im Raster, um einen teilweise bedruckten Bogen
  weiterzunutzen.
- **Testdruck**: Rahmen + Positionsnummer, für eine Ausrichtungsprobe auf
  Normalpapier.

#### Geräteplanung

Ergänzt die Abgangsliste um alles ohne physischen Kanal (Sensoren,
Wetterstationen, Bedienelemente) — unabhängig von einer Gruppenadresse.
Aktoren gehören weiterhin in die Abgangsliste.

1. Je Raum Geräte hinzufügen (**Anzahl** legt mehrere unabhängige Einträge
   an); physische Adresse bei Anzahl 1 direkt, sonst über **Bearbeiten**.
   Ohne passenden Raum: **Geräte ohne Raum** je Geschoss.
2. **Stückliste** oben: Gesamtanzahl je Gerät (inkl. Aktoren) fürs
   Bestellen. **Nicht bestellen** markiert bereits vorhandene Geräte.
3. **PDF herunterladen** exportiert die Bestellliste.
4. **Geräte je Raum → PDF herunterladen** exportiert alle Geräte gruppiert
   nach Geschoss/Raum als Installationsreferenz.
5. **PA automatisch zuordnen** — siehe Abgangsliste, Punkt 7.

#### Verteilerplanung

Visuelles Hutschienen-Layout je Verteiler (12 TE pro Reihe).

- **+ Verteiler anlegen**: Geschoss/Raum, Name, Reihenzahl. Ort später über
  Gebäudestruktur ändern.
- Je Reihe: **+ RCD**/**+ LS** (Platzhalter) oder **+ Gerät...** (Aktoren
  desselben Geschosses ohne Verteiler-Platzierung, brauchen eine gesetzte
  **TE**-Breite im Geräte-Katalog).
- Pfeile sortieren um, **×** entfernt (Gerät bleibt in der Abgangsliste).
- **PDF herunterladen** exportiert alle Verteiler.

#### Pflichtenheft

Die frühe Leistungsbeschreibung — nur Planung, keine Testergebnisse.
**Inhalt** zeigt den PDF-Aufbau mit Stand je Abschnitt. **Vorschau**/
**PDF herunterladen** wie gehabt. Enthält immer Vorbemerkungen sowie
Funktionen/Geräte je Raum; Stockwerk-/Raumverzeichnis und Geräteliste
optional (Setup → Pflichtenheft, dort auch der anpassbare
Vorbemerkungen-Text mit einfacher Formatierung: `##`/`###` Überschrift,
`**Text**` fett/als Unterüberschrift auf eigener Zeile, `*Text*` kursiv,
`---` Trennlinie, `- ` Aufzählung).

**Per E-Mail senden** verschickt das PDF direkt (Setup → E-Mail).

#### Funktionscheckliste

Digitaler Testfortschritt vor Ort: jede Funktion antippen, sobald getestet
— sofort gespeichert, mit Zeitstempel. **Bestätigung: Funktionen
getestet** erfasst eine Unterschrift (Systemintegrator, Kunde optional).
**PDF herunterladen**/**Per E-Mail senden** wie gehabt.

#### Übergabe-Checkliste

Zweites, allgemeines Formular fürs Übergabegespräch (Funktionsprüfung,
Kundengespräch, Anlagenübergabe) — nur die Arbeit des Systemintegrators,
keine physische Installation. Je Punkt ein Schalter **Ja | Nein | Nicht
nötig** plus Bemerkungsfeld, direkt gespeichert.

Unten: digitale **Unterschrift** für Systemintegrator und Kunde/Betreiber
(Finger/Maus, mit Zeitstempel, jederzeit neu unterschreibbar). **PDF
herunterladen**/**Per E-Mail senden** wie gehabt.

#### Klärungsliste

Interne Liste für Fragen/Aufgaben/Notizen (z.B. beim Kundentermin) —
erscheint nicht im Pflichtenheft, optional in der Dokumentation.

- Jeder Eintrag: **Typ**, optional Raum/Punkt. **Status**
  (offen/geklärt/abgelehnt) und **Antwort** direkt in der Liste editierbar.
- Der Tab-Button zeigt die Anzahl offener Einträge; seit >7 Tagen offene
  gelten als veraltet (gelbes Badge/Hinweis).
- **Offene Punkte weitergeben**: durchnummerierte Liste der offenen
  Einträge — **Als Text kopieren**, **PDF herunterladen**, oder
  **Per E-Mail senden**.

#### Handbücher

Hersteller-Handbücher für im Projekt verwendete Geräte mit hinterlegtem
Link (Geräte-Katalog → Handbücher). **Herunterladen** speichert eine
eigene Kopie; danach **Ansehen**/**Löschen**. **Alle herunterladen** holt
alle fehlenden auf einmal.

#### Dokumentation

Die Abschlussdokumentation. **Inhalt** zeigt Stand je Kapitel (Kontrolle
vor der Übergabe). **PDF herunterladen** fasst den Pflichtenheft-Inhalt mit
den Checklisten-Ergebnissen und optional Handbücher-Nachweis, Abgangsliste,
Verteilerplanung, Gruppenadressen, Klärungsliste und Geräte je Raum
zusammen (Auswahl: Setup → Dokumentation). Gruppenadressen steht immer
zuletzt (meist der längste Abschnitt). Seite 1 hat ein klickbares
Inhaltsverzeichnis. **Per E-Mail senden** wie gehabt.

### Geräte Katalog

Zwei Unterreiter: **Katalog** und **Handbücher**.

Globaler Katalog für alle Projekte — Aktoren, Sensoren, Wetterstationen,
Bedienelemente usw. Je Eintrag: **Hersteller**, **Modell**, **Gruppe**,
optionale **Beschreibung**; nur bei Gruppe "Aktor": **Type**/**Kanäle**
(muss zum Kanaltyp eines Funktionstyps passen); optional **TE**
(Hutschienenbreite) für hutschienenmontierte Geräte.

Suchfeld filtert live. **Bearbeiten** lädt einen Eintrag ins Formular.
**⭳/⭱ Katalog exportieren/importieren (JSON)** sichern/teilen den Katalog
(Import gleicht nach Hersteller+Modell ab, führt zusammen). **Katalog
leeren** entfernt alles Unbenutzte (Sicherheitsabfrage); bleibt er leer,
füllt sich beim nächsten Neustart automatisch der Standardkatalog wieder.
**⟲ Standard-Katalog importieren** stösst diesen Import jederzeit manuell
an (zeigt vorher, was sich ändert).

#### Handbücher

Je Gerät ein optionales Feld für die Handbuch-URL, speichert sofort beim
Verlassen des Felds. Grundlage für den projekteigenen Unterreiter
Handbücher.

### Zeiterfassung

Arbeitszeit je Projekt — rein intern, in keinem Export/keiner
Projektsicherung enthalten, bleibt bei Projektlöschung erhalten.

- **Start/Stopp** im Programmkopf, läuft weiter über Tab-/Seitenwechsel
  (immer höchstens eine Erfassung gleichzeitig).
- **Rundung** auf das eingestellte Raster (Setup → Zeiterfassung, Standard
  15 Min., mindestens eine Rastereinheit je Eintrag).
- **Übersicht**: Summen, filterbar nach Projekt und **Abgerechnet**.
- **Bearbeiten/Nachtragen** je Eintrag; Bis vor Von = über Mitternacht.
- **Abgerechnet**-Häkchen je Eintrag, oder **Alle angezeigten als
  abgerechnet markieren** auf einmal.
- **PDF herunterladen**: Stundennachweis der aktuellen Auswahl.

### Setup

Firma, Kategorien, Funktionstypen, Zentral-/Allgemeinfunktions-Vorlagen,
Pflichtenheft, Dokumentation, E-Mail, Backup, Zeiterfassung als eigene
Unterreiter — je einer speichert nur seine eigenen Felder.

- **Firma** — Name/Adresse/Kontakt/Logo, erscheint im Programmkopf. Schalter
  **"Firmenlogo/-daten auf PDF-Exporten anzeigen"** gilt für alle Exporte.
- **Kategorien** — nur umbenennbar, Reihenfolge/Anzahl fest (KNX-
  Hauptgruppennummern). **Namen exportieren/importieren (JSON)**.
- **Funktionstypen** — wiederverwendbare Definitionen mit Datenpunkten,
  Blockumfang, **Kanaltyp**. **Alle löschen** (unbenutzte) / **Exportieren/
  Importieren (JSON)**.
- **Zentral-/Allgemeinfunktions-Vorlagen** — automatisch erzeugte Blöcke:
  `scope: building` (projektweit), `floor` (je Geschoss), `room_multi` (je
  Raum ab Mindestanzahl Punkte — bei Rollo vorkonfiguriert). "Aussen-/
  unbeheizte Geschosse überspringen" bei `floor`. **Alle löschen**/
  **Exportieren/Importieren (JSON)**.
- Eine Kategorie erzeugt ihre Hauptgruppe nur, wenn sie im Projekt
  tatsächlich genutzt wird.
- **Pflichtenheft** — Vorbemerkungen-Text plus drei Checkboxen für den
  PDF-Inhalt.
- **Dokumentation** — acht Checkboxen für den PDF-Inhalt (Funktions-/
  Übergabe-Checkliste, Handbücher standardmässig an; der Rest aus, da er
  ein Projekt schnell lang macht).
- **E-Mail** — SMTP-Zugangsdaten für **Per E-Mail senden** (manuell
  ausgelöst, nie automatisch). **Test-E-Mail senden** prüft die
  Einstellungen. Sendedialog: vorausgefüllte Empfänger, CC, Freitext.
- **Backup** — automatische und/oder manuelle Sicherung der kompletten
  Datenbank auf NAS und/oder Nextcloud (Details: `DEPLOYMENT.md`), mit
  Wiederherstellen je Sicherung oder aus hochgeladener Datei. Jeder Weg
  legt vorher eine Sicherung des aktuellen Stands an und prüft die Datei,
  bevor sie übernommen wird.
- **Zeiterfassung** — **Aktiv** schaltet den Tab ein/aus; **Rundung**
  (minutengenau/15/30 Min., gilt nur für neue Einträge).

### Update

Prüft nur auf Klick. **⟲ Nach Updates suchen** zeigt den Stand und ggf.
**⭱ Update installieren**. Darunter das **Änderungsprotokoll**
(`CHANGELOG.md`). Details zum Mechanismus: `DEPLOYMENT.md`.

## PDF-Exporte

Alle Exporte teilen dieselbe Gestaltung (Banner-Titelkopf, Tabellenoptik,
Fusszeile mit **Seite X von Y**). Ist "Firmenlogo/-daten auf PDF-Exporten
anzeigen" (Setup → Firma) aktiv, erscheinen zusätzlich Firmenname/Logo auf
Seite 1 und Adresse/Kontakt in der Fusszeile jeder Seite.

## Hinweise / Einschränkungen

- Einzelbenutzer, keine Authentifizierung — nur im eigenen Netzwerk.
- Keine `.knxproj`-Manipulation, nur der CSV-Importweg.
- ETS-Import überschreibt passende Einträge, löscht aber nie fehlende —
  Aufräumen bei Bedarf manuell in ETS.
- Reservierte `res`-Blöcke sind Ihre bestehende Konvention; reicht ein
  Blockumfang nicht, verschiebt das Tool einfach nachfolgende Punkte statt
  aufzufüllen — Blockgrössen grosszügig wählen.
- Eine Kategorie-Hauptgruppe (und ihre Zentralvorlagen) erscheint nur, wenn
  sie im Projekt tatsächlich genutzt wird.
- "Aussen-/unbeheizte Geschosse überspringen" gilt je Vorlage einzeln.
