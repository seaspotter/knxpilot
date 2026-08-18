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
  geöffnetes Projekt zeigt einen Arbeitsbereich mit zehn Unterreitern
  (Übersicht, Gebäudestruktur, Funktionen, Gruppenadressen, Abgangsliste,
  Labels, Geräteplanung, Verteilerplanung, Pflichtenheft, Klärungsliste),
  die alle am selben Projekt arbeiten.
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

**Projektübersicht** (oben in der Projektliste, sobald mindestens ein
Projekt existiert): drei Karten fassen den Stand über alle Projekte
hinweg zusammen — **Projekte gesamt** (Anzahl je Status als klickbare
Badges, ein Klick trägt den Status direkt ins Suchfeld ein), **Offene
Klärungen** (Gesamtzahl, plus wie viele davon seit mehr als 7 Tagen
unbeantwortet sind — jedes betroffene Projekt einzeln aufgelistet, ein
Klick öffnet es direkt im Unterreiter Klärungsliste) und **Ohne
Struktur** (Projekte ohne ein einziges angelegtes Geschoss, ein Klick
öffnet sie direkt im Unterreiter Gebäudestruktur).

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
beim Unterreiter Übersicht, der auf einen Blick zeigt, wie weit acht der
übrigen Unterreiter gediehen sind (mit direktem Sprung dorthin per Klick)
— nur Labels fehlt hier, da es keine sinnvolle Kurzkennzahl dafür gibt.

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
   frei). Über **Bearbeiten** lassen sich Geschoss, Standortbezeichnung
   und physische Adresse jederzeit nachträglich korrigieren — z.B. wenn
   Aktoren zuerst angelegt und die physische Adresse erst später bei der
   Schaltschrankmontage feststeht. Der Aktortyp selbst lässt sich dabei
   nicht ändern (dafür den Aktor löschen und neu mit dem richtigen Typ
   anlegen), um bereits zugeordnete Abgänge nicht durch einen abweichenden
   Kanaltyp/-anzahl zu verwaisen.
5. Jeder **Abgang** (eine Zeile je benötigtem physischen Ausgang) erscheint
   darunter mit einer Auswahl aller Kanäle passender Aktoren. Einen manuell
   wählen, oder **Alle automatisch zuordnen** klicken, um jeden noch nicht
   zugeordneten Abgang dem ersten freien passenden Kanal zuzuweisen.
   **Automatisch zuordnen mischt dabei nie Geschosse** — ein Abgang im EG
   wird nur einem Aktor im EG zugeordnet, selbst wenn dessen Kanäle voll
   sind und ein Aktor im OG noch frei wäre. Aktoren ohne zugewiesenes
   Geschoss werden von der Automatik ebenfalls nicht verwendet; solche
   Fälle bitte manuell zuordnen. Bei **Rollo/Jalousie**-Abgängen bevorzugt
   die Automatik zusätzlich ausgerichtete Kanalpaare (A+B, C+D, E+F, G+H):
   landen zwei Abgänge desselben Raums auf demselben Aktor, werden sie auf
   ein gemeinsames Paar gelegt statt auf zwei beliebige freie Kanäle — viele
   Jalousieaktoren teilen sich pro Kanalpaar einen gemeinsamen Eingang
   (z.B. für die Fahrtzeitmessung).
6. **CSV herunterladen** exportiert eine Tabelle mit den Spalten
   `Geschoss, Raum/UV, Aktor, Physikalische Adr., Kanal, Funktion` — jeder
   Kanal jedes Aktors wird aufgeführt, unbelegte mit `RESERVE` markiert.
   **PDF herunterladen** exportiert dieselben Daten als formatiertes, nach
   Geschoss und Aktor gegliedertes PDF (ein Geschoss pro Seite).
7. **PA automatisch zuordnen** (auch im Unterreiter Geräteplanung
   verfügbar — beide wirken projektweit auf beide Tabs) vergibt
   physikalische Adressen für alle Geräte ohne eine, nach fester
   Reihenfolge: Systemgeräte (Netzteile, Linienkoppler — Adressen 0-5),
   dann je Geschoss ein Block für Aktoren, dann je Geschoss ein Block für
   Sensoren/Bedienelemente, dann ein Block für Aussen-Geräte (Geschoss als
   **Aussen/unbeheizt** markiert — Wetterstationen zuerst, danach der
   Rest). Jeder Block beginnt an der nächsten Zehnerstelle und reserviert
   so viele Zehnerblöcke wie für die tatsächliche Gerätezahl nötig (z.B.
   startet ein Geschoss mit 12 Aktoren bei `.10`, das nächste dann bei
   `.30` statt `.20`, da zwei volle Zehnerblöcke gebraucht wurden) — so
   bleibt Platz für spätere Ergänzungen, ohne bestehende Adressen zu
   verschieben. Das Bereich.Linie-Präfix (Standard `1.1`) ist vor dem
   Klick änderbar. Bereits gesetzte Adressen werden nie verändert;
   Geräte ohne zugewiesenes Geschoss werden übersprungen und gemeldet.

#### Labels

Bedruckt einen Etikettenbogen für die Schaltschrankbeschriftung — nutzt
dieselben Aktoren/Kanäle wie die Abgangsliste, deshalb ein eigener
Unterreiter direkt daneben statt eine Karte darin.

- **Format**: aktuell nur **Avery Zweckform L6037** (25,4 × 10 mm,
  189 Etiketten je Bogen) — weitere Formate lassen sich später ergänzen,
  die Auswahl ist bewusst als Dropdown angelegt.
- **Inhalt**: **Aktoren** (ein Etikett je Aktor: physikalische Adresse +
  Standortbezeichnung — genau die Felder, die beim Aktor-Anlegen in der
  Abgangsliste eingegeben wurden) oder **Kanäle** (ein Etikett je Kanal:
  physikalische Adresse + Kanalbuchstabe, plus die zugeordnete Funktion
  bzw. `RESERVE`).
- **Startposition**: auf ein Etikett im Positionsraster klicken, um dort
  mit dem Druck zu beginnen — praktisch, um einen bereits teilweise
  bedruckten Bogen weiter zu nutzen, ohne schon bedruckte Etiketten zu
  überschreiben.
- **Testdruck** druckt zusätzlich einen Rahmen und die Positionsnummer
  auf jedes Etikett — empfohlen für einen ersten Ausdruck auf
  Normalpapier, gegen einen leeren Bogen gehalten, um die Ausrichtung zu
  prüfen, bevor echte Etiketten bedruckt werden.

#### Geräteplanung

Ergänzt die Abgangsliste (die nur Aktoren mit physischen Kanälen betrifft):
hier wird zusätzlich festgelegt, welche übrigen Geräte — Sensoren,
Wetterstationen, Bedienelemente usw. — in welchem Raum verbaut werden,
unabhängig davon ob dafür eine Gruppenadresse existiert. Die Gruppe
**Aktor** steht hier bewusst nicht zur Auswahl — Aktoren gehören in die
Abgangsliste, wo sie mit Geschoss, Standort, physischer Adresse und
Kanalzuordnung erfasst werden (und trotzdem mit in der Stückliste unten
erscheinen, siehe Punkt 2).

1. Für jeden Raum Geräte hinzufügen — **Anzahl** legt fest, wie viele
   Geräte auf einmal angelegt werden, jedes davon als eigener,
   unabhängiger Eintrag (nicht eine gemeinsame Stückzahl). Bei Anzahl 1
   lässt sich die **physische Adresse** direkt beim Anlegen eintragen; bei
   mehreren auf einmal ist das Feld deaktiviert (eine einzelne Adresse
   lässt sich nicht sinnvoll auf mehrere neue Geräte verteilen) — dann
   über **Bearbeiten** je Eintrag einzeln nachtragen. Genauso praktisch,
   wenn Geräte zuerst grob geplant und die Adresse erst später (z.B. bei
   der Verkabelung) feststeht.
2. Oben erscheint automatisch eine **Stückliste** — die Gesamtanzahl jedes
   benötigten Geräts über das ganze Projekt hinweg, nach Gruppe sortiert.
   Praktisch für Bestellung oder Angebotskalkulation. Zählt sowohl hier
   geplante Geräte **als auch** die bereits in der Abgangsliste
   angelegten Aktoren mit — ein Aktor muss also nicht doppelt erfasst
   werden, um in der Gesamtübersicht zu erscheinen.
3. **PDF herunterladen** exportiert diese Stückliste als Bestellliste, plus
   eine Aufschlüsselung je Raum bzw. — bei Aktoren aus der Abgangsliste —
   je Standortbezeichnung, jeweils mit physischer Adresse, sofern gesetzt.
4. **PA automatisch zuordnen** vergibt physikalische Adressen für alle
   Geräte im Projekt ohne eine — siehe Abgangsliste, Punkt 7, für die
   genaue Reihenfolge/Logik; hier wie dort wirkt der Klick projektweit auf
   beide Tabs gleichzeitig.

#### Verteilerplanung

Ein einfaches visuelles Layout des Schaltschranks (Hutschiene) je Geschoss.
Ein **Verteiler** gehört zu einem Geschoss und hat eine feste Anzahl Reihen
— jede Reihe ist immer 12 TE (Teilungseinheiten, 1 TE = 18 mm) breit.

- **+ Verteiler anlegen** — Geschoss, Name und Anzahl Reihen wählen. Über
  **Bearbeiten** lassen sich beide später ändern (die Reihenzahl nicht
  unter die höchste noch belegte Reihe, sonst Fehlermeldung).
- Jede Reihe zeigt ihre Elemente als proportional breite Kästchen (nach
  TE), freier Platz erscheint gestrichelt. Drei Buttons je Reihe:
  - **+ RCD (4 TE)** / **+ LS (1 TE)** — einfache, benannte Platzhalter
    mit Standardbreite. Aktuell ohne Bezug zu bestimmten Abgängen/Kanälen
    — reine Platzhalter für den Hutschienenplatz, keine eigene Auswertung
    (siehe `ROADMAP.md`).
  - **+ Gerät...** — Auswahl aus den bereits in der Abgangsliste
    angelegten Aktoren desselben Geschosses, die noch in keinem Verteiler
    platziert sind (Anzeige: Aktortyp, Standort, physikalische Adresse
    und TE-Breite, z.B. "MDT AKD-0401.02 · Technik · 1.1.13 (6 TE)"). Nur
    Geräte mit gesetzter **TE**-Breite im Geräte-Katalog erscheinen zur
    Auswahl — fehlt sie, zuerst dort nachtragen. Ein Gerät lässt sich nur
    in einem Verteiler gleichzeitig platzieren.
- Reicht der freie Platz einer Reihe nicht, meldet das Tool die noch
  freie TE-Zahl statt stillschweigend zu überfüllen.
- Über die Pfeile an jedem Kästchen lässt sich die Reihenfolge innerhalb
  einer Reihe anpassen; **×** entfernt ein Element wieder (das zugehörige
  Gerät selbst bleibt in der Abgangsliste erhalten — nur die Platzierung
  im Verteiler wird gelöscht). Ein Gerätekästchen zeigt Aktortyp und
  physikalische Adresse (falls gesetzt); beim Zeigen mit der Maus
  erscheinen zusätzlich TE-Breite und Standortbezeichnung als Tooltip.
- **PDF herunterladen** exportiert alle Verteiler des Projekts als
  formatiertes PDF — je Verteiler eine Reihenübersicht, optisch analog
  zur Bildschirmansicht. Lässt sich zusätzlich optional ins
  Pflichtenheft-PDF aufnehmen (siehe unten, Setup → Pflichtenheft).

#### Pflichtenheft

Dokumentiert, was für das Projekt tatsächlich vereinbart/umgesetzt wurde —
gedacht als Referenz für Kunde und Elektriker, getrennt von den technischen
GA-/Verdrahtungsdetails. Eine Textvorschau zeigt sofort, was im PDF stehen
wird; **PDF herunterladen** erzeugt ein mehrseitiges Dokument mit:

- einem **Vorbemerkungen**-Abschnitt (Begriffserklärungen, allgemeine
  Bedienphilosophie, Funktionsübersicht je Gewerk, Prioritäts-/
  Sicherheitsfunktionen — mit sinnvollem Standardtext vorbelegt, siehe
  unten),
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
und **Abgangsliste**, **Klärungsliste** sowie **Gruppenadressen**
(standardmässig aus, da sie ein Projekt schnell sehr lang machen können —
gezielt für den Einzelfall dazuschalten). Gruppenadressen steht dabei
immer als letzter Abschnitt im PDF, auch wenn die anderen optionalen
Abschnitte weiter oben ausgewählt sind — es ist meist der längste (jede
einzelne Adresse als Tabellenzeile) und passt daher eher ans Ende als
mitten zwischen die eher erzählenden Abschnitte. Dort lässt sich auch der
Vorbemerkungen-Text anpassen und über ein eigenes Kontrollkästchen
ein-/ausblenden, ohne den Text dabei zu verlieren — eine einfache
Formatierung ist möglich: eine Leerzeile trennt Absätze, `##` oder `###`
für eine Überschrift, eine Zeile die nur aus `**Text**` besteht für eine
kleinere Unterüberschrift, eine Zeile die nur aus `*Text*` besteht für
einen kursiven Hinweis/Fussnote, `---` für eine Trennlinie, `- ` am
Zeilenanfang für Aufzählungspunkte, und `**Text**` mitten im Satz für
Fettdruck.

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
- Ein offener Eintrag, der seit mehr als 7 Tagen unbeantwortet ist, gilt
  als **veraltet**: er bekommt ein zusätzliches Badge ("12 Tage offen"),
  der Unterreiter-Button färbt sich gelb, und oben in der Liste erscheint
  ein Hinweis ("⚠ N Einträge sind seit mehr als 7 Tagen unbeantwortet").
  Dieselbe Kennzahl fliesst auch in die Projektübersicht auf der
  Projektliste ein (siehe oben).

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
- **TE** (optional) — Breite auf der Hutschiene in Teilungseinheiten
  (1 TE = 18 mm), laut Datenblatt des Herstellers. Nur für
  hutschienenmontierte Geräte relevant (z.B. Aktoren, Netzteile,
  IP-Interfaces) — bei Tastern/Sensoren/Wetterstationen leer lassen.
  Grundlage für die künftige Verteiler-Layout-Funktion (siehe
  `ROADMAP.md`), aktuell nur zur Erfassung, noch ohne eigene Auswertung.

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
Neustart automatisch wieder der mitgelieferte Standard-Startkatalog
eingefügt (siehe unten) — bei Bedarf vorher den eigenen Katalog
exportieren, um ihn danach wieder zu importieren.

Bei einer frischen Installation (leerer Katalog) wird beim ersten Start
automatisch ein Startkatalog gängiger KNX-Geräte eingefügt (u.a. MDT,
Busch-Jaeger, Theben, Elsner Elektronik, Gira, Phoenix Contact, Hörmann,
Enertex), eingelesen aus den mitgelieferten Dateien unter
`docs/templates/geraete-katalog_<hersteller>.json` im Repository — ein
File je Hersteller (`_mdt`, `_bj`, `_phoenix`, `_elsner`, `_theben`,
`_gira`, `_enertex`, `_hoermann`), automatisch eingesammelt beim Start
(`load_bundled_actor_type_defaults()` in `backend/db.py`) — eine weitere
Herstellerdatei nach diesem Namensschema abzulegen reicht, ohne
Codeänderung. Das passiert nur, wenn die Tabelle beim Start leer ist — ein
bereits befüllter Katalog wird dadurch nie automatisch überschrieben, auch
nicht bei einem späteren Neustart (z.B. nachdem einzelne Standardgeräte
absichtlich gelöscht wurden).

**⟲ Standard-Katalog importieren** stößt genau diesen Import manuell noch
einmal an, jederzeit später — z.B. um neu hinzugekommene Standardgeräte
nachzuziehen, ohne die mitgelieferten Dateien einzeln herunterladen und
importieren zu müssen. Gleicht wie jeder andere Import nach (Hersteller,
Modell) ab (vorhandene werden aktualisiert, fehlende ergänzt) — bewusst
gelöschte Geräte kommen dadurch **nicht von allein zurück**, nur auf
diesen expliziten Klick hin.

### Setup

Firma, Kategorien, Funktionstypen, Zentral-/Allgemeinfunktions-Vorlagen,
Pflichtenheft und Backup sind eigene Unterreiter innerhalb des Setup-Tabs,
nicht alle gleichzeitig sichtbar.

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
  Standardtext vorbelegt, siehe Abschnitt *Pflichtenheft* oben) sowie
  sieben Kontrollkästchen, die steuern, was im Pflichtenheft-PDF erscheint:
  Vorbemerkungen, Stockwerk-/Raumverzeichnis, Geräteliste (alle drei
  standardmässig an), Gruppenadressen, Abgangsliste, Verteilerplanung
  und Klärungsliste (standardmässig aus). Gilt global für alle Projekte,
  wie der Rest des Firmenprofils.
- **Backup** — automatische und/oder manuelle (**Jetzt sichern**) Sicherung
  der kompletten Datenbank (alle Projekte, Geräte-Katalog, restliches
  Setup — nicht nur ein einzelnes Projekt) auf ein NAS/gemountetes
  Verzeichnis und/oder Nextcloud (WebDAV), beide unabhängig voneinander
  aktivierbar. Bei aktiver automatischer Sicherung läuft im Hintergrund
  eine einfache Prüfung (alle 15 Minuten: ist seit der letzten Sicherung
  mehr Zeit vergangen als das eingestellte Intervall?), keine externe
  Aufgabenplanung nötig. Je Ziel wird nur die eingestellte Anzahl
  neuester Sicherungen behalten, ältere werden automatisch gelöscht.
  Details zur NAS-Einbindung und den Nextcloud-Zugangsdaten:
  [`DEPLOYMENT.md`](./DEPLOYMENT.md). Darunter: **Vorhandene Sicherungen**
  listet alles in jedem aktivierten Ziel — NAS und Nextcloud — mit
  Herunterladen/Wiederherstellen je Zeile (ist Nextcloud aktiviert, aber
  seine Liste nicht abrufbar, z.B. wegen falscher URL/Zugangsdaten, wird
  das als eigene Meldung angezeigt, ohne die NAS-Liste zu verstecken).
  **Sicherung wiederherstellen (Datei hochladen)** stellt zusätzlich aus
  jeder hochgeladenen Datei wieder her, auch von ausserhalb der beiden
  konfigurierten Ziele. Alle drei Wege ersetzen die komplette laufende
  Datenbank und starten die App danach automatisch neu — vorher wird
  immer zuerst eine Sicherung des aktuellen Stands angelegt, und eine
  Datei wird vor der Übernahme geprüft (muss wie eine echte
  KNXpilot-Datenbank aussehen), damit weder ein Fehlklick noch eine
  falsche Datei etwas endgültig zerstört.

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
