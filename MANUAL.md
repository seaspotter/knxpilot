# KNXpilot – Bedienungsanleitung

Diese Seite ist auch direkt in der App verfügbar (Tab **Hilfe**) — dort
identisch gerendert, hier nur als Referenz/zum Durchsuchen auf GitHub.

## Adressierungsmodell (entspricht Ihren echten Projekten)

- **Hauptgruppe** → Funktionskategorie: `Allgemein, Beleuchtung,
  Steckdosen, Heizung, Rollo, Tore`
- **Mittelgruppe** → `Zentralfunktionen` + eine je Geschoss
- **Untergruppe** → ein Adressblock je physischem Punkt:
  `{Raum} {Label} {Suffix}`

Jeder Punkt reserviert einen **festen Adressblock** (Standard 5, oder 10 bei
Jalousien mit Lamelle) und füllt ungenutzte Plätze mit `res` für spätere
Erweiterungen auf — genau wie in Ihren bestehenden Projekten.

**Dieses Schema ist fest im Tool verankert, nicht nur eine Voreinstellung.**
Kategorien lassen sich zwar umbenennen (siehe Setup → Kategorien), aber die
Zuordnung Hauptgruppe=Kategorie/Mittelgruppe=Geschoss/Untergruppe=Punkt
selbst ist es nicht — sie steckt in `backend/ga_logic.py`s
`build_ga_tree()`, in der Bedeutung von `categories.order_idx` als
KNX-Hauptgruppennummer (0–5, daher auch keine neuen Kategorien
hinzufügbar), und im gesamten Zentral-/Allgemeinfunktions-Vorlagensystem
(`scope: building/floor/room_multi` geht von "Kategorie = Hauptgruppe"
aus). Ein anderes Schema (z.B. Geschoss als Hauptgruppe, Kategorie als
Mittelgruppe) wäre kein Setup-Schalter, sondern eine andere
Adressierungs-Engine — u.a. weil KNX-Hauptgruppen nur 0–31 erlauben,
Mittelgruppen sogar nur 0–7 (bei 3-Ebenen-Adressierung): mit Geschossen
als Hauptgruppe bräuchte jede Kategorie eine Mittelgruppennummer
0–7, was bei mehr als 8 Kategorien nicht mehr aufgeht. Dieses Tool bildet
bewusst genau ein Schema ab (das der realen Projekte, aus denen es
entstanden ist), kein Baukasten für beliebige Konventionen.

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

## Die fünf Tabs

- **Projekte** — Projekte anlegen/suchen/öffnen; ein Klick auf den kleinen
  Pfeil ▾ daneben öffnet ein Menü mit **Neues Projekt** und
  **Projekt öffnen** (öffnet ein Suchfenster mit allen Projekten, wählt
  direkt eines aus — auch von einem anderen bereits offenen Projekt aus,
  ohne es vorher schliessen zu müssen) als Abkürzung von überall in der
  App aus. Ist ein Projekt geöffnet, zeigt eine kleine Marke 📁 im
  Programmkopf (neben der Versionsnummer) jederzeit, welches — ein Klick
  darauf springt dorthin, das **×** daneben schliesst es direkt von
  überall aus, ohne erst zum Projekte-Tab wechseln zu müssen. Ein
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
- **Hilfe** — diese Anleitung, direkt in der App.

### Projekte

**Projektliste** (Standardansicht): ein Suchfeld filtert live nach Name,
Kunde, Standort, Status und Bestellnummer, die als Badges neben jedem
Projektnamen erscheinen. **+ Neues Projekt** öffnet ein Formular (Name,
Kunde, Standort, Status, Bestellnummer, Kommentar — alle Felder ausser
Name optional) und wechselt nach dem Anlegen direkt in den Arbeitsbereich
des neuen Projekts. Das ⭱-Symbol oben rechts in der Kopfzeile öffnet ein
Popup zum **Wiederherstellen aus einer JSON-Sicherung**: Datei auswählen,
importieren — legt daraus ein neues Projekt an (siehe Gruppenadressen
unten); existiert bereits ein Projekt mit gleichem Namen, wird der Import
als "<Name> (imported)" gespeichert statt es zu überschreiben. Jede Zeile
der Liste hat ausserdem **Öffnen**, **Duplizieren** und **Löschen**
— Duplizieren legt sofort eine vollständige Kopie an ("<Name> (Kopie)",
bei mehrfachem Duplizieren fortlaufend nummeriert), ohne Umweg über eine
Datei.

**Öffnen** eines Projekts (aus der Liste, oder über das Suchfenster
**Projekt öffnen** im ▾-Menü) zeigt dessen Arbeitsbereich (die
Projektliste wird dabei ausgeblendet, nicht darunter weiter angezeigt):
oben die Projekt-Metadaten mit **Bearbeiten**-Button (ändert
Name/Kunde/Standort/Status/Bestellnummer/Kommentar nachträglich),
daneben zwei Symbole — **⭳** (als JSON sichern) und **⧉** (duplizieren,
wechselt direkt in die neue Kopie) — sowie **× Schliessen**. Ein zweites
Projekt über **Projekt öffnen** auszuwählen wechselt direkt dorthin, ohne
das erste vorher schliessen zu müssen. **× Schliessen** (oder das **×**
an der 📁-Marke im Programmkopf) kehrt zur Projektliste zurück, ohne
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
- **⭳** (im Projektkopf oben, unterreiterübergreifend sichtbar) speichert
  die komplette Projektdefinition (Metadaten, Geschosse, Räume, Punkte,
  Sonderadressen) als `.json`-Datei — getrennt von der ETS-CSV, gedacht
  zum Sichern oder Umziehen eines Projekts zwischen Installationen (über
  das ⭱-Symbol in der Projektliste wieder einspielbar). Beim
  Wiederherstellen werden Funktionstypen/Kategorien per Name mit der
  Zielinstallation abgeglichen; was nicht übereinstimmt, wird
  übersprungen und gemeldet, nie einfach angenommen. Für eine schnelle
  Kopie auf derselben Installation (z.B. als Vorlage für ein ähnliches
  Objekt) gibt es stattdessen **Duplizieren** (⧉ im Projektkopf, oder als
  Button direkt in der Projektliste) — legt ohne Datei-Umweg sofort eine
  komplette Kopie an.

#### Abgangsliste

Sobald ein Projekt Räume und Punkte enthält, kennt das Tool bereits jeden
physischen Ausgang, der benötigt wird (jeder Schalt-, Dimm-, LED-, Jalousie-
und Heizkanal). Dieser Unterreiter macht daraus eine Verdrahtungsliste für
den Elektriker — getrennt von der ETS-Gruppenadressen-CSV: die eine dient
der Busprogrammierung, die andere der Schaltschrank-Verdrahtung.

1. Jeder Funktionstyp hat einen **Kanaltyp** (z.B. `Schalten`, `Dimmen`, `LED`,
   `Rollo`, `Heizung`, `Tor`, siehe Setup-Tab) und **benötigte Kanäle**
   (meist 1).
2. Im Geräte-Katalog-Tab die verwendeten Aktoren anlegen, mit einem
   **Type**, der zum Kanaltyp passt (siehe unten).
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
wird; **PDF herunterladen** erzeugt ein mehrseitiges Dokument mit:

- einem **Vorbemerkungen**-Abschnitt (allgemeine Erklärung, wie
  Schalten/Dimmen/Jalousie/Heizung bedient werden),
- den geplanten Funktionen und Geräten je Geschoss/Raum — jede einzelne
  Funktion mit einer leeren **Getestet**-Checkbox zum Abhaken vor Ort nach
  der Inbetriebnahme (rein papierbasiert — es wird nichts im Tool
  gespeichert, da KNXpilot nicht nachhält, welcher Taster welche Funktion
  auslöst; das ist Sache der ETS-Programmierung),
  sowie einer Übersicht der Zentral-/Allgemeinfunktionen (ebenfalls mit
  Getestet-Checkbox) — diese beiden sind immer enthalten.

Zusätzlich lassen sich im Setup-Tab unter *Pflichtenheft* (siehe unten)
weitere Abschnitte optional dazuschalten: **Stockwerk- und
Raumverzeichnis** sowie **Geräteliste** (Stückliste, standardmässig an),
und **Gruppenadressen**, **Abgangsliste** sowie **Klärungsliste**
(standardmässig aus, da sie ein Projekt schnell sehr lang machen können —
gezielt für den Einzelfall dazuschalten). Dort lässt sich auch der
Vorbemerkungen-Text anpassen und über ein eigenes Kontrollkästchen
ein-/ausblenden, ohne den Text dabei zu verlieren.

Daneben steht **Übergabe-Checkliste herunterladen** — ein zweites,
weitgehend allgemeines PDF (Sichtprüfung, Funktionsprüfung,
Kundengespräch, Anlagenübergabe, je mit Ja/Nein/Nicht-nötig-Checkboxen und
Bemerkungsspalte, plus Unterschriftenzeilen für Errichter und
Kunde/Betreiber) für das Übergabegespräch vor Ort — nur Projektname
wird automatisch eingesetzt, der Rest ist ein fester, wiederverwendbarer
Fragenkatalog.

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
dieselbe Datei mehrfach zu importieren ist unbedenklich, und mehrere
verschiedene Herstellerkataloge lassen sich nacheinander importieren:
sie werden zusammengeführt, nicht ersetzt. **Katalog leeren** entfernt
den kompletten Katalog auf einmal (mit Sicherheitsabfrage) — Geräte, die
bereits in einem Projekt verwendet werden, bleiben dabei erhalten und
werden übersprungen. Bleibt der Katalog danach leer, wird beim nächsten
Neustart automatisch wieder der Standard-Startkatalog eingefügt (siehe
unten) — bei Bedarf vorher den eigenen Katalog importieren.

Bei einer frischen Installation (leerer Katalog) wird beim ersten Start
automatisch ein Startkatalog gängiger KNX-Geräte eingefügt (u.a. MDT,
Busch-Jaeger, Theben, Elsner Elektronik, Gira, Phoenix Contact, Hörmann —
siehe `DEFAULT_ACTOR_TYPES` in `backend/db.py`). Das passiert nur einmalig, wenn
die Tabelle leer ist — ein bereits befüllter oder bewusst geleerter Katalog
wird dadurch nie überschrieben. Genau dieser Startkatalog liegt zusätzlich
als Datei unter `docs/templates/geraete-katalog.json` im Repository —
importierbar wie jede andere Katalogdatei, z.B. nach einem **Katalog
leeren**, ohne alles neu eintippen zu müssen.

### Setup

Firma, Kategorien, Funktionstypen, Zentral-/Allgemeinfunktions-Vorlagen und
Pflichtenheft sind eigene Unterreiter innerhalb des Setup-Tabs, nicht alle
gleichzeitig sichtbar.

- **Firma** — Name, Adresse, Telefon, E-Mail, Website und ein Logo,
  einmalig hinterlegt. Erscheint als Badge im Programmkopf neben dem
  KNXpilot-Logo (Logo + Name), sobald etwas hinterlegt ist. Zusätzlich
  gibt es einen globalen Schalter **"Firmenlogo/-daten auf
  PDF-Exporten anzeigen"** — gilt für alle PDF-Exporte gleichzeitig,
  kein Umschalten je Export nötig (siehe *PDF-Exporte* weiter unten).
  Das Logo wird beim Hochladen automatisch auf den sichtbaren
  Bildinhalt zugeschnitten (entfernt transparente/weisse Rahmen um das
  eigentliche Motiv), damit es in der kleinen Kopfzeilen-Badge nicht
  winzig wirkt.
- **Kategorien** — die 6 Hauptgruppen, vorbelegt; der Name jeder Kategorie
  lässt sich über **Bearbeiten** umbenennen, Reihenfolge (=
  Hauptgruppennummer) und Anzahl bleiben fest — daher kein
  Hinzufügen/Löschen hier (siehe Adressierungsmodell oben). **Namen
  exportieren/importieren (JSON)** sichert bzw. stellt nur die 6 Namen
  wieder her (abgeglichen nach Hauptgruppennummer, nie nach Reihenfolge
  in der Datei) — z.B. um versehentliche Umbenennungen rückgängig zu
  machen. Vorlage: `docs/templates/kategorien.json`.
- **Funktionstypen** — wiederverwendbare Definitionen wie "Licht (Dimmen)",
  "Rollo (einfach)", "Jalousie (mit Lamelle)", "Heizkreis", jeweils mit
  Datenpunkten, reserviertem Blockumfang und einem **Kanaltyp** (z.B.
  `Schalten`, `Dimmen`, `Rollo`, `Heizung`, `Tor`), der den Punkt mit
  passenden Aktortypen für die Abgangsliste verknüpft. Die Vorbelegung ist
  ein Vorschlag, kein festes Schema — jederzeit anpassbar, und **Alle
  löschen** entfernt auf einmal alle noch nicht in einem Projekt
  verwendeten Funktionstypen (mit Sicherheitsabfrage), um eigene von
  Grund auf anzulegen. Bereits verwendete bleiben dabei erhalten.
  **Exportieren/Importieren (JSON)** sichert bzw. lädt einen kompletten
  Satz Funktionstypen (Abgleich nach Kategorie+Name — erneutes
  Importieren aktualisiert bestehende statt sie zu duplizieren); Vorlage
  mit den mitgelieferten Standard-Funktionstypen:
  `docs/templates/funktionstypen.json`.
- **Zentral-/Allgemeinfunktions-Vorlagen** — automatisch erzeugte Blöcke
  (**Alle löschen** entfernt hier ausnahmslos alle, da nichts anderes im
  Tool auf eine bestimmte Vorlage verweist; **Exportieren/Importieren
  (JSON)** funktioniert wie bei Funktionstypen, Vorlage:
  `docs/templates/zentral-vorlagen.json`):
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
- **Pflichtenheft** — der Vorbemerkungen-Text (mit einem sinnvollen
  Standardtext vorbelegt: kurzer/langer Tastendruck, Beleuchtung,
  Rollladen/Jalousie, Heizung, Zentral-/Wetterfunktionen) sowie sechs
  Kontrollkästchen, die steuern, was im Pflichtenheft-PDF erscheint:
  Vorbemerkungen, Stockwerk-/Raumverzeichnis, Geräteliste (alle drei
  standardmässig an), Gruppenadressen, Abgangsliste und Klärungsliste
  (standardmässig aus). Gilt global für alle Projekte,
  wie der Rest des Firmenprofils.

### Update

Prüft **nur auf Klick** — nichts läuft automatisch im Hintergrund.
**⟲ Nach Updates suchen** zeigt den aktuellen Stand und, falls auf GitHub
eine neuere Version vorliegt, einen **⭱ Update installieren**-Button.
Schlägt die Prüfung fehl, zeigt der Tab die tatsächliche Fehlermeldung an
statt kommentarlos "kein Update verfügbar" zu behaupten. Voraussetzungen
auf dem Server und wie der Mechanismus intern funktioniert (git pull +
Neustart, kein Image-Rebuild für reine Codeänderungen) siehe
[`DEPLOYMENT.md`](./DEPLOYMENT.md).

Darunter zeigt der Tab das **Änderungsprotokoll** dieses Tools
(`CHANGELOG.md`), damit ersichtlich ist, was sich seit der letzten
Installation geändert hat, ohne extra auf GitHub nachsehen zu müssen.

## PDF-Exporte

Alle PDF-Exporte (Abgangsliste, Geräteliste, Pflichtenheft,
Übergabe-Checkliste) nutzen dieselbe Gestaltung: ein dunkler
Banner-Titelkopf, eine einheitliche Tabellenoptik, und eine Fusszeile mit
Projektname sowie **Seite X von Y** auf jeder Seite. Der gemeinsame Code
dafür liegt in `backend/pdf_design.py` (`pdf_styles()`,
`pdf_title_banner()`, `pdf_table_style()`, `make_numbered_canvas()`) —
Änderungen dort wirken sich auf alle Exporte gleichzeitig aus.

Ist im Setup-Tab unter *Firma* der Schalter "Firmenlogo/-daten auf
PDF-Exporten anzeigen" aktiv, ergänzt `company_header_block()` oben auf
Seite 1 Firmenname und Logo (neben dem Titel-Banner), während
`company_footer_line()` Adresse, Telefon, E-Mail und Website als
eigene, zentrierte Zeile unterhalb von "Seite X von Y" auf **jeder**
Seite einfügt. Ist der Schalter aus oder kein Firmenprofil hinterlegt,
liefern beide Funktionen einfach nichts zurück — die Aufrufer in den
drei Router-Dateien brauchen dafür kein `if`.

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
