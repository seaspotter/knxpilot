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

## Die Tabs

- **Projekte** — Projekte anlegen/suchen/öffnen; ein Klick auf den kleinen
  Pfeil ▾ daneben öffnet ein Menü mit **Neues Projekt** und
  **Projekt öffnen** (öffnet ein Suchfenster mit allen Projekten, wählt
  direkt eines aus — auch von einem anderen bereits offenen Projekt aus,
  ohne es vorher schliessen zu müssen) als Abkürzung von überall in der
  App aus. Ist ein Projekt geöffnet, zeigt eine kleine Marke 📁 im
  Programmkopf (neben der Versionsnummer) jederzeit, welches — ein Klick
  darauf springt dorthin, das **×** daneben schliesst es direkt von
  überall aus, ohne erst zum Projekte-Tab wechseln zu müssen. Ein
  geöffnetes Projekt zeigt einen Arbeitsbereich mit vierzehn Unterreitern
  (Übersicht, Gebäudestruktur, Funktionen, Gruppenadressen, Abgangsliste,
  Labels, Geräteplanung, Verteilerplanung, Pflichtenheft,
  Funktionscheckliste, Übergabe-Checkliste, Klärungsliste, Handbücher,
  Dokumentation), die alle am selben Projekt arbeiten.
- **Geräte Katalog** — globaler Gerätekatalog (Aktoren, Sensoren,
  Bedienelemente usw.), gemeinsam für alle Projekte genutzt.
- **Zeiterfassung** — einfache Arbeitszeiterfassung je Projekt
  (Start/Stopp im Programmkopf), mit Abgerechnet-Markierung und
  Stundennachweis als PDF. Lässt sich unter Setup → Zeiterfassung
  abschalten, dann ist der Tab ausgeblendet.
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
— Duplizieren legt sofort eine Kopie der Planung an ("<Name> (Kopie)",
bei mehrfachem Duplizieren fortlaufend nummeriert), ohne Umweg über eine
Datei (was genau kopiert wird: siehe Gruppenadressen, ⭳/Duplizieren).

**Öffnen** eines Projekts (aus der Liste, oder über das Suchfenster
**Projekt öffnen** im ▾-Menü) zeigt dessen Arbeitsbereich (die
Projektliste wird dabei ausgeblendet, nicht darunter weiter angezeigt):
oben die Projekt-Metadaten mit **Bearbeiten**-Button (ändert
Name/Kunde/Standort/Status/Bestellnummer/Kommentar nachträglich, sowie
**E-Mail** und **Weitere Empfänger** — die Adresse(n), die beim
E-Mail-Versand von PDF-Exporten als "An" vorausgefüllt werden, siehe
weiter unten die einzelnen Unterreiter),
daneben zwei Symbole — **⭳** (als JSON sichern) und **⧉** (duplizieren,
wechselt direkt in die neue Kopie) — sowie **× Schliessen**. Ein zweites
Projekt über **Projekt öffnen** auszuwählen wechselt direkt dorthin, ohne
das erste vorher schliessen zu müssen. **× Schliessen** (oder das **×**
an der 📁-Marke im Programmkopf) kehrt zur Projektliste zurück, ohne
etwas zu löschen — beim nächsten Öffnen startet der Arbeitsbereich wieder
beim Unterreiter Übersicht, der auf einen Blick zeigt, wie weit zwölf der
übrigen Unterreiter gediehen sind (mit direktem Sprung dorthin per Klick)
— nur Labels fehlt hier, da es keine sinnvolle Kurzkennzahl dafür gibt.

Darunter, im Bereich **Dateien**: ein paar Referenzdateien zu diesem
Projekt hochladen (z.B. Baupläne, ein ETS-Export) — Datei auswählen,
**Hochladen**, danach mit **Herunterladen**/**Löschen** je Zeile
verwalten (max. 25 MB je Datei). Bewusst keine vollständige
Dokumentenablage: die Dateien liegen direkt in der Datenbank und sind
damit automatisch Teil der Datenbanksicherung (Setup → Backup) und der
JSON-Projektsicherung (⭳/⭱), beim Duplizieren (⧉) aber nicht — die Pläne
gehören zum Original-Objekt. Gerätehandbücher gehören bewusst **nicht**
hierher — die haben ihren eigenen Unterreiter Handbücher (siehe unten).

#### Gebäudestruktur

Nur das Gebäude selbst — welche Funktionen wo landen, ist Sache des
Unterreiters Funktionen weiter unten.

Die Struktur erscheint als Baum wie in ETS: Geschoss → Raum → Verteiler.
Jedes Geschoss lässt sich über den Pfeil davor auf- und zuklappen (der
Browser merkt sich das).

- Geschosse (Stockwerke) hinzufügen; ein Geschoss als **Aussen/unbeheizt**
  markieren (z.B. "Aussen", "Garage"), wenn es von entsprechend markierten
  Vorlagen ausgeschlossen werden soll.
- Räume je Geschoss hinzufügen — unter den Räumen des Geschosses einzeln
  (**+ Raum**, oder Enter), oder über **Mehrere...** eine Liste von
  Raumnamen (ein Name pro Zeile) auf einmal einfügen.
- **✎** benennt ein Geschoss oder einen Raum um, **×** löscht es.
- **Ziehen und Ablegen** (am Griff ⠿ oder der ganzen Zeile): einen Raum
  an eine andere Stelle oder in ein anderes Geschoss ziehen (auf einen
  anderen Raum: davor/danach, auf eine Geschosszeile: ans Ende dieses
  Geschosses), Geschosse untereinander umsortieren, einen Verteiler auf
  ein Geschoss oder in einen Raum ziehen. Der Raum nimmt dabei alles mit —
  Funktionen, Geräte, Klärungen, einen Verteiler darin. Ohne Maus (Tablet,
  Tastatur) macht **⇄** an jeder Zeile dasselbe über eine Auswahl.
- Weil die Mittelgruppe das Geschoss ist und die Adressblöcke der
  Reihenfolge der Räume folgen, ändert Verschieben meist Gruppenadressen.
  Dann fragt KNXpilot vorher nach und nennt die Anzahl; wurde das Projekt
  schon nach ETS exportiert, zeigt Gruppenadressen → "Änderungen seit dem
  letzten ETS-Export" danach genau, was in ETS nachzuziehen ist.
  Verschiebungen ohne Auswirkung auf Gruppenadressen passieren ohne
  Rückfrage.
- **Verteiler** erscheinen im Baum unter ihrem Geschoss bzw. Raum (angelegt
  werden sie im Unterreiter Verteilerplanung, ein Klick auf den Namen
  springt dorthin).
- **Löschen** fragt immer nach und listet dabei genau auf, was mitgelöscht
  wird (Räume, Funktionen, Kanalzuordnungen, geplante Geräte,
  Sonderadressen, Klärungslisten-Einträge) und was nur seine
  Geschoss-Zuordnung verliert (Aktoren, Verteiler). Dasselbe gilt beim
  Löschen eines ganzen Projekts.
- **KNX-Linien (optional)** — nur nötig, wenn die Anlage über
  Linienkoppler in mehrere TP-Linien geteilt wird, z.B. eine Linie je
  Wohnung plus eine Aussenlinie. Im aufklappbaren Bereich unter den
  Geschossen Bereich, Linie und einen Namen eintragen (**+ Linie
  hinzufügen**); danach erscheint an jedem Geschoss eine Linienauswahl,
  und abweichend davon an jedem Raum ("Linie wie Geschoss") sowie an
  jedem Aktor in der Abgangsliste. Was nirgends zugeordnet ist, gehört zur
  ersten Linie (**Standard**). Die Tabelle zeigt je Linie die Anzahl
  Geräte und Hinweise: mehr als 64 Geräte (bzw. kaum Reserve ab 55),
  kein Linienkoppler oder keine Busspannungsversorgung geplant — erkannt
  an der Katalog-Beschreibung ("Koppler"/"Coupler",
  "Spannungsversorgung"/"KNX PowerSupply"). Gruppenadressen bleiben davon
  unberührt, sie gelten in KNX projektweit. Löschen einer Linie lässt alle
  darauf zugeordneten Geschosse/Räume/Aktoren auf die Standardlinie
  zurückfallen; bereits vergebene physikalische Adressen bleiben stehen.
  Ohne eigene Linien ist das Projekt eine einzige Linie wie bisher.

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
  (Hauptgruppe → Mittelgruppe → Adresse), jedes Mal frisch erzeugt —
  **Alle aufklappen**/**Alle einklappen** klappen ihn komplett auf bzw. zu.
- **CSV für ETS6 herunterladen** exportiert dieselben Adressen als
  ETS6-kompatible CSV-Datei.
- **Änderungen seit dem letzten ETS-Export** (oben im Unterreiter): Jeder
  CSV-Download merkt sich den exportierten Stand. Kommen danach Räume oder
  Funktionen dazu, zeigt diese Karte, was in ETS noch nachzutragen ist —
  in der Reihenfolge, in der man es am besten abarbeitet:
  1. **Verschoben** — eine Funktion liegt jetzt auf einer anderen Adresse
     (typisch: eine neue Funktion schiebt alle folgenden Adressen im
     Geschoss nach hinten). In ETS die Adresse der bestehenden
     Gruppenadresse ändern, statt sie neu anzulegen — so bleiben ihre
     Verknüpfungen erhalten. Von oben nach unten abarbeiten, dann ist die
     Zieladresse jeweils schon frei.
  2. **Neu** — in ETS anlegen.
  3. **Geändert** — gleiche Adresse, neuer Name oder DPT (z.B. ein
     umbenannter Raum oder ein bisher reservierter "res"-Platz).
  4. **Entfernt** — in ETS löschen.

  Beim nächsten CSV-Download beginnt die Liste von vorn. Wurde das
  ETS-Projekt auf anderem Weg aktualisiert (oder für ältere Projekte, die
  noch keinen gemerkten Export haben), setzt **Aktuellen Stand als in ETS
  übernommen markieren** den Stand ohne Download.
- **⭳** (im Projektkopf oben, unterreiterübergreifend sichtbar) speichert
  das **komplette Projekt** als `.json`-Datei — getrennt von der ETS-CSV,
  gedacht zum Sichern oder Umziehen eines Projekts zwischen
  Installationen (über das ⭱-Symbol in der Projektliste wieder
  einspielbar): Metadaten, Geschosse/Räume/Funktionen, Sonderadressen,
  KNX-Linien, Aktoren samt Kanalzuordnung und physikalischen Adressen,
  geplante Geräte, "Nicht bestellen"-Markierungen, Verteiler, Klärungen,
  die Haken und Bemerkungen beider Checklisten, Unterschriften, der Stand
  des letzten ETS-Exports, Projektdateien und abgelegte Handbücher.
  Nur die Zeiterfassung ist nie dabei (rein intern). Beim Wiederherstellen
  werden Funktionstypen/Kategorien/Vorlagen per Name und Geräte per
  Hersteller + Typ mit der Zielinstallation abgeglichen; was nicht
  übereinstimmt, wird übersprungen und gemeldet, nie einfach angenommen.
  Für eine schnelle Kopie auf derselben Installation (z.B. als Vorlage für
  ein ähnliches Objekt) gibt es stattdessen **Duplizieren** (⧉ im
  Projektkopf, oder als Button direkt in der Projektliste) — kopiert die
  **Planung** (alles oben bis einschliesslich Verteiler), aber nicht, was
  zum Original-Objekt gehört: keine Klärungen, Checklisten-Haken,
  Unterschriften, kein ETS-Export-Stand, keine Dateien oder Handbücher.
  Die Kopie startet also ungetestet und "noch nie nach ETS exportiert".

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
   KNX-Adresse wie `1.1.2`). Die Liste ist nach Geschossen in der
   Reihenfolge der Gebäudestruktur sortiert (innerhalb eines Geschosses
   in der Reihenfolge des Anlegens, Aktoren ohne Geschoss zuletzt), wie die
   Abgänge darunter. Jeder Aktor zeigt eine kleine visuelle
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
   zugeordneten Abgang dem ersten freien passenden Kanal zuzuweisen. Vorher
   zeigt ein Dialog genau, welcher Abgang auf welchen Aktorkanal käme (und
   was nicht zuordenbar ist) — erst nach **Zuordnen** wird gespeichert.
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
   verfügbar — beide wirken projektweit auf beide Tabs) zeigt zuerst eine
   Vorschau (welche Adresse an welches Gerät in welchem Raum geht) und
   vergibt nach Bestätigung physikalische Adressen für alle Geräte ohne
   eine, nach fester
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
   Hat das Projekt eigene **KNX-Linien** (siehe Gebäudestruktur), wird
   jede Linie für sich nach diesem Schema nummeriert, mit ihrer eigenen
   Bereich.Linie-Adresse statt des Präfix-Felds (dort steht dann "je
   Linie"): z.B. EG-Wohnung `1.1.10`…, OG-Wohnung `1.2.10`…. Nur Geschosse
   mit Geräten auf der jeweiligen Linie belegen dort einen Block. Ein
   Linienkoppler kommt unter den Systemgeräten zuerst und erhält so die
   `.0` seiner Linie.

#### Labels

Bedruckt einen Etikettenbogen für die Schaltschrankbeschriftung — ein
Etikett je Gerät mit physikalischer Adresse, projektweit: Aktoren aus der
Abgangsliste sowie Sensoren/Bedienelemente/Wetterstationen usw. aus der
Geräteplanung, deshalb ein eigener Unterreiter direkt daneben statt eine
Karte darin.

- **Format**: aktuell nur **Avery Zweckform L6037** (25,4 × 10 mm,
  189 Etiketten je Bogen) — weitere Formate lassen sich später ergänzen,
  die Auswahl ist bewusst als Dropdown angelegt.
- **Inhalt**: ein Etikett je Gerät mit physikalischer Adresse, sortiert
  nach Adresse — als zweite Zeile bewusst nur der Ort (Aktoren mit ihrer
  Standortbezeichnung, Geräte aus der Geräteplanung mit ihrem Raum- bzw.
  Geschossnamen), kein Gerätetyp. Geräte ohne physikalische Adresse
  erscheinen nicht.
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
   der Verkabelung) feststeht. Passt ein Gerät zu keinem bestimmten Raum
   (z.B. eine Wetterstation an der Fassade oder ein Aussen-Bewegungsmelder),
   lässt es sich stattdessen direkt unter **Geräte ohne Raum** je Geschoss
   anlegen — funktioniert genau wie die Raum-Geräte, nur ohne eigens dafür
   einen (unpassenden) Raum erstellen zu müssen.
2. Oben erscheint automatisch eine **Stückliste** — die Gesamtanzahl jedes
   benötigten Geräts über das ganze Projekt hinweg, alphabetisch nach
   Gerät (Hersteller + Typ) sortiert — ebenso im PDF.
   Praktisch für Bestellung oder Angebotskalkulation. Zählt sowohl hier
   geplante Geräte **als auch** die bereits in der Abgangsliste
   angelegten Aktoren mit — ein Aktor muss also nicht doppelt erfasst
   werden, um in der Gesamtübersicht zu erscheinen. Jeder Eintrag hat ein
   Kontrollkästchen **Nicht bestellen** — für Geräte, die bereits vorhanden
   sind (z.B. eine übrige Wetterstation oder ein Tor-Aktor aus einem
   anderen Projekt): bleibt in der Stückliste sichtbar (mit dem Hinweis
   "Bereits vorhanden"), fällt aber aus der Bestellliste im PDF-Export
   heraus.
3. **PDF herunterladen** exportiert die Bestellliste — Hersteller, Typ,
   die Beschreibung aus dem Geräte Katalog und Gruppe in getrennten Spalten,
   plus Anzahl. Die Stückliste im Pflichtenheft und in der Dokumentation
   sieht genau gleich aus. Als "Nicht bestellen"
   markierte Geräte stehen separat darunter ("Bereits vorhanden, nicht
   bestellt"), nicht in der eigentlichen Bestelltabelle. Enthält bewusst
   keine Raumaufschlüsselung mehr (die steht im Pflichtenheft, falls dort
   gewünscht) — dieser Export ist als reine Liste für den Lieferanten
   gedacht.
4. Im Bereich **Geräte je Raum** exportiert **PDF herunterladen** stattdessen
   alle Geräte des Projekts (inkl. der Aktoren aus der Abgangsliste)
   gruppiert nach Geschoss/Raum, mit Gruppe, Hersteller, Typ,
   Beschreibung (aus dem Geräte Katalog) und physischer Adresse — als Installationsreferenz für die Ausführung vor
   Ort, getrennt von der Bestellliste oben. Lässt sich zusätzlich optional
   ins Dokumentation-PDF aufnehmen (siehe unten, Setup → Dokumentation).
5. **PA automatisch zuordnen** vergibt physikalische Adressen für alle
   Geräte im Projekt ohne eine — siehe Abgangsliste, Punkt 7, für die
   genaue Reihenfolge/Logik; hier wie dort wirkt der Klick projektweit auf
   beide Tabs gleichzeitig.

#### Verteilerplanung

Ein einfaches visuelles Layout des Schaltschranks (Hutschiene) je Geschoss.
Ein **Verteiler** gehört zu einem Geschoss (optional zu einem Raum darin,
z.B. Technikraum) und hat eine feste Anzahl Reihen — jede Reihe ist immer
12 TE (Teilungseinheiten, 1 TE = 18 mm) breit.

- **+ Verteiler anlegen** — Geschoss oder Raum, Name und Anzahl Reihen
  wählen. Den Ort ändert man später in der Gebäudestruktur (Ziehen oder
  **⇄**); im PDF steht er als "Geschoss / Raum" hinter dem Namen. Über
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
  Dokumentation-PDF aufnehmen (siehe unten, Setup → Dokumentation).

#### Pflichtenheft

Die frühe, kundenseitige Leistungsbeschreibung: was wurde vereinbart? Rein
auf die Planungsphase fokussiert — bewusst ohne Testergebnisse oder
Ausführungsdetails (dafür: Funktionscheckliste, Übergabe-Checkliste,
Dokumentation, siehe unten). Der Unterreiter zeigt unter **Inhalt** die
Abschnitte des PDFs in ihrer Reihenfolge — je Abschnitt, ob er enthalten
ist und was drinsteht (z.B. "2 Geschosse · 6 Räume", "9 Gerätetypen · 18
Stück", Räume noch ohne Funktionen orange). **Vorschau** öffnet das PDF
zum Lesen in einem neuen Browser-Tab, **PDF herunterladen** speichert es.
Das PDF ist ein mehrseitiges Dokument mit:

- einem **Vorbemerkungen**-Abschnitt (Begriffserklärungen, allgemeine
  Bedienphilosophie, Funktionsübersicht je Gewerk, Prioritäts-/
  Sicherheitsfunktionen — mit sinnvollem Standardtext vorbelegt, siehe
  unten),
- den geplanten Funktionen und Geräten je Geschoss/Raum sowie einer
  Übersicht der Zentral-/Allgemeinfunktionen (immer enthalten, ohne
  Checkbox-Spalte — was tatsächlich getestet wurde, hält stattdessen die
  Funktionscheckliste digital fest).

Zusätzlich lassen sich im Setup-Tab unter *Pflichtenheft* (siehe unten)
das **Stockwerk- und Raumverzeichnis** sowie die **Geräteliste**
(Stückliste) optional dazuschalten (beide standardmässig an). Dort lässt
sich auch der Vorbemerkungen-Text anpassen und über ein eigenes
Kontrollkästchen ein-/ausblenden, ohne den Text dabei zu verlieren — eine
einfache Formatierung ist möglich: eine Leerzeile trennt Absätze, `##`
oder `###` für eine Überschrift, eine Zeile die nur aus `**Text**` besteht
für eine kleinere Unterüberschrift, eine Zeile die nur aus `*Text*`
besteht für einen kursiven Hinweis/Fussnote, `---` für eine Trennlinie,
`- ` am Zeilenanfang für Aufzählungspunkte, und `**Text**` mitten im Satz
für Fettdruck.

Neben **PDF herunterladen** steht **Per E-Mail senden**, um das PDF direkt
aus KNXpilot zu verschicken statt es herunterzuladen und manuell
anzuhängen — siehe Setup → E-Mail weiter unten.

#### Funktionscheckliste

Der digitale Testfortschritt vor Ort: jede geplante Funktion (je
Geschoss/Raum sowie die Zentral-/Allgemeinfunktionen) lässt sich hier
direkt auf dem Handy antippen, sobald sie getestet ist — kein Ausdrucken
und Abhaken auf Papier nötig, der Haken wird sofort im Projekt
gespeichert. Jeder Raum ist eine kleine Tabelle: vorne die Kategorie,
dann die Funktion, rechts **getestet** mit dem Kästchen; ein Tipp
irgendwo auf die Zeile genügt, erledigte Zeilen werden ausgegraut. Neben
jedem Haken steht, wann er gesetzt wurde (Datum und Uhrzeit des letzten
Antippens — kein vollständiger Verlauf); im PDF steht das Datum unter dem
Kästchen. Am Ende bestätigt **Bestätigung: Funktionen getestet** die
Prüfung mit Unterschrift auf dem Bildschirm: Systemintegrator, der Kunde
optional — getrennt von den Unterschriften der Übergabe-Checkliste.
Beides erscheint im PDF und im entsprechenden Kapitel der Dokumentation;
fehlt die Unterschrift des Systemintegrators, weist der Dokumentation-Tab
unter Inhalt darauf hin. **PDF herunterladen** erzeugt daraus eine Momentaufnahme zum
Weitergeben, ist aber nicht die primäre Arbeitsweise. **Per E-Mail
senden** verschickt dieselbe Momentaufnahme direkt (siehe Setup → E-Mail).

#### Übergabe-Checkliste

Ein zweites, weitgehend allgemeines digitales Formular für das
Übergabegespräch vor Ort (Funktionsprüfung, Kundengespräch,
Anlagenübergabe) — bewusst auf die Arbeit des Systemintegrators
beschränkt (Programmierung/Inbetriebnahme, Kundengespräch, Übergabe),
ohne Punkte zur physischen Elektroinstallation (Verdrahtung, Montage,
E-Check usw.), die Sache des Elektrikers ist. Gleiche Tabellenoptik wie
die Funktionscheckliste: je Punkt rechts ein Schalter **Ja | Nein | Nicht
nötig** (die gewählte Antwort farbig; nochmals antippen hebt sie wieder
auf), daneben wann sie gesetzt wurde, darunter ein Bemerkungsfeld —
direkt hier ausgefüllt und gespeichert; nur der
Projektname ist projektspezifisch, der restliche Fragenkatalog ist fest
und wiederverwendbar.

Ganz unten lässt sich für **Systemintegrator** und **Kunde/Betreiber** je
eine **digitale Unterschrift** erfassen — **Unterschreiben** öffnet ein
Unterschriftenfeld, das sich direkt mit dem Finger (oder der Maus)
beschreiben lässt; **Speichern** legt sie im Projekt ab, mit Zeitstempel
("Unterschrieben am ..."). **Neu unterschreiben** überschreibt eine
vorhandene Unterschrift jederzeit, **Löschen** entfernt sie wieder — kein
Ausdrucken und Scannen nötig. **PDF herunterladen** erzeugt daraus eine
Momentaufnahme: mit bereits erfassten digitalen Unterschriften erscheint
dort die echte Unterschrift samt Zeitstempel, für noch fehlende bleibt
eine leere Unterschriftenzeile zum Ausdrucken/handschriftlichen
Unterschreiben. **Per E-Mail senden** verschickt diese Momentaufnahme
direkt, z.B. um das unterschriebene Protokoll gegenzeichnen zu lassen
(siehe Setup → E-Mail).

#### Klärungsliste

Interne Arbeitsliste für Fragen, Aufgaben und Notizen, die z.B. bei einem
Kundentermin anfallen (etwa "Tasterfarbe schwarz oder weiss?") — erscheint
**nicht** im Pflichtenheft-Export, sondern optional (siehe unten) im
Dokumentation-Export. Die noch offenen Punkte lassen sich zusätzlich
gezielt weitergeben (siehe *Offene Punkte weitergeben* unten).

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
- **Offene Punkte weitergeben** — um offene Fragen mit Kunde oder
  Elektriker zu klären. Enthält nur Einträge mit Status *offen*, nach Raum
  gruppiert und durchnummeriert (gleiche Nummern in Text und PDF, damit
  man sich im Gespräch auf "Punkt 3" beziehen kann):
  - **Als Text kopieren** legt die Liste in die Zwischenablage, zum
    Einfügen in eine eigene E-Mail oder Nachricht. Eine bereits
    notierte Antwort steht als "Bisher: …" darunter.
  - **PDF herunterladen** erzeugt das PDF "Offene Punkte" mit den
    Spalten Nr., Typ, Frage/Aufgabe und **Antwort** — bereits notierte
    Antworten sind eingetragen, sonst bleibt die Spalte zum
    handschriftlichen Ausfüllen frei.
  - **Per E-Mail senden** verschickt dieses PDF direkt (wie bei den
    anderen Exporten, siehe Setup → E-Mail).

#### Handbücher

Hersteller-Handbücher für die im Projekt tatsächlich verwendeten Geräte —
eigener Unterreiter, bewusst getrennt vom Bereich Dateien im Unterreiter
Übersicht: Dateien sind, was Sie selbst hochladen, Handbücher sind, was
KNXpilot für Sie herunterlädt.

Die Liste zeigt jedes verwendete Gerät, das im Geräte-Katalog unter
**Handbücher** einen Link hat (siehe dort) — Geräte ohne hinterlegten Link
erscheinen hier gar nicht erst. Je Gerät:

- **Herunterladen** lädt das PDF von der hinterlegten URL und speichert es
  als eigene Kopie in diesem Projekt — nur auf diesen Klick hin, nie
  automatisch.
- Nach dem Herunterladen ersetzen **Ansehen** (öffnet das PDF direkt in
  einem neuen Browser-Tab) und **Löschen** den Button.
- **Alle herunterladen** oben lädt alle noch fehlenden auf einmal;
  bereits vorhandene werden dabei übersprungen, keine Duplikate.

Der Dokumentation-Export (siehe unten) kann optional einen kurzen
Handbücher-Nachweis enthalten (welches Gerät hat einen Link, welches ist
bereits heruntergeladen) — die PDFs selbst bleiben aber immer hier im
Unterreiter, nicht im Dokumentation-PDF eingebettet.

#### Dokumentation

Die vollständige Abschlussdokumentation, gedacht für das Ende des
Projekts. Unter **Inhalt** stehen alle Kapitel in PDF-Reihenfolge mit
ihrem Stand — gleichzeitig eine Kontrolle vor der Übergabe: z.B. "9 / 36
getestet", "7 / 19 beantwortet · 0 / 2 Unterschriften", "8 / 10
Handbücher im Projekt abgelegt" oder offene Klärungen erscheinen orange;
ausgeschaltete Kapitel grau mit Verweis auf Setup → Dokumentation.
**Vorschau** öffnet das PDF in einem neuen Browser-Tab. **PDF herunterladen** fasst den Pflichtenheft-Inhalt (was
vereinbart wurde, als eigener, klar mit "Pflichtenheft" überschriebener
Abschnitt) mit optional den tatsächlichen Ergebnissen der Funktions- und
Übergabe-Checkliste, optional einem Handbücher-Nachweis sowie optional
Abgangsliste, Verteilerplanung, Gruppenadressen, Klärungsliste und Geräte
je Raum zusammen — welche Abschnitte enthalten sind, wird im Setup-Tab
unter *Dokumentation* gesteuert (siehe unten; Funktionscheckliste,
Übergabe-Checkliste und Handbücher sind dort standardmässig an).
Gruppenadressen steht dabei immer als letzter Abschnitt im PDF, auch wenn
andere optionale Abschnitte weiter oben ausgewählt sind — es ist meist
der längste (jede einzelne Adresse als Tabellenzeile) und passt daher
eher ans Ende als mitten zwischen die eher erzählenden Abschnitte.

Der Handbücher-Abschnitt listet nur, für welche im Projekt verwendeten
Geräte ein Handbuch-Link hinterlegt ist und ob es bereits in den
Unterreiter Handbücher heruntergeladen wurde (✓/leere Box je Gerät) — die
PDFs selbst werden **nicht** in dieses Dokument eingebettet, sie bleiben
im projekteigenen Unterreiter Handbücher zum Ansehen/Herunterladen.

Die erste Seite zeigt eine kurze Einleitung sowie ein
**Inhaltsverzeichnis** mit einem Eintrag je enthaltenem Abschnitt — jeder
Eintrag ist ein echter klickbarer PDF-Link, der beim Anklicken direkt zum
jeweiligen Abschnitt springt (funktioniert in den meisten PDF-Readern,
z.B. Acrobat Reader, Firefox, Chrome/Edge — nicht notwendigerweise in
jeder mobilen PDF-App).

**Per E-Mail senden** verschickt die vollständige Abschlussdokumentation
direkt aus KNXpilot (siehe Setup → E-Mail).

### Geräte Katalog

Zwei Unterreiter: **Katalog** (Geräte anlegen/bearbeiten, siehe unten) und
**Handbücher** (Hersteller-PDF-Links je Gerät, siehe weiter unten).

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
diesen expliziten Klick hin. Vor dem Import zeigt ein Dialog genau, was
sich ändert: welche Geräte neu dazukommen und bei welchen Geräten welches
Feld von welchem auf welchen Wert geändert wird (z.B. eine selbst
angepasste Beschreibung) — ist nichts zu tun, passiert nichts. Dasselbe
gilt für **Importieren (JSON)** einer eigenen Katalogdatei.

#### Handbücher

Je Gerät ein optionales Feld für die URL des Hersteller-PDF-Handbuchs —
bleibt es leer, wird es einfach nicht genutzt. Läuft komplett getrennt vom
Katalog-Formular (kein zusätzliches Feld in der ohnehin dichten
Geräte-Zeile) und speichert bei jedem Feld einzeln beim Verlassen
(kein separater Speichern-Button nötig). Ein Suchfeld filtert wie im
Katalog live nach Hersteller/Modell/Gruppe.

Diese Links sind die Grundlage für den eigenen **Handbücher**-Unterreiter
in jedem Projekt-Arbeitsbereich (siehe dort) — nur Geräte mit hinterlegtem
Link erscheinen dort zum Herunterladen.

### Zeiterfassung

Einfache Erfassung der eigenen Arbeitszeit je Projekt — für den eigenen
Überblick und die Abrechnung. **Rein intern:** die Zeiten erscheinen in
keinem Projekt-Export (Pflichtenheft, Dokumentation, Checklisten,
Geräteliste usw.), nicht in der JSON-Projektsicherung/-Duplizierung und
nicht im E-Mail-Versand. Sie liegen in einer eigenen, projektübergreifenden
Tabelle: wird ein Projekt gelöscht, bleiben seine erfassten Zeiten
erhalten. Teil der Datenbanksicherung (Setup → Backup) sind sie
selbstverständlich.

- **Start/Stopp** — ist ein Projekt geöffnet, erscheint im Programmkopf
  ein **▶ Start**-Knopf. Während die Zeit läuft, zeigt der Kopf den
  (gerundeten) Startzeitpunkt, eine laufende Uhr und **■ Stopp** — auch
  nach dem Schliessen des Projekts, einem Tab-Wechsel oder einem
  Neuladen der Seite. Es läuft immer höchstens eine Zeiterfassung; läuft
  sie für ein anderes Projekt, steht dessen Name daneben.
- **Rundung** — Start und Stopp werden beim Speichern auf die nächste
  Marke des in Setup → Zeiterfassung gewählten Rasters gerundet
  (Standard 15 Minuten: Start um 12:04 → 12:00, Stopp um 12:55 → 13:00).
  Ein Eintrag zählt immer mindestens eine Rastereinheit (12:04–12:06 →
  12:00–12:15). Alternativ 30 Minuten oder minutengenau.
- **Übersicht** — Summe je Projekt und Liste aller Einträge (Datum,
  Projekt, Von, Bis, Dauer, Notiz), filterbar nach Projekt und nach
  **Abgerechnet** (Alle / Nicht abgerechnet / Abgerechnet). Summe und
  Summe je Projekt folgen den Filtern.
- **Bearbeiten / Nachtragen** — jeder Eintrag lässt sich bearbeiten
  (Projekt, Datum, Von, Bis, Notiz) oder löschen; **+ Eintrag
  nachtragen** erfasst Zeiten nachträglich, z.B. wenn Start vergessen
  wurde. Die Uhrzeit-Auswahl bietet nur Zeiten im eingestellten Raster
  (bei 15 Minuten also :00/:15/:30/:45). Liegt Bis vor Von, gilt der
  Eintrag als über Mitternacht.
- **Abgerechnet** — Häkchen je Eintrag, um bereits in Rechnung gestellte
  Zeiten zu markieren. **Alle angezeigten als abgerechnet markieren**
  markiert nach Rückfrage alle aktuell sichtbaren, noch offenen Einträge
  auf einmal. Typischer Ablauf: Projekt wählen, Filter "Nicht
  abgerechnet", PDF herunterladen, Rechnung schreiben, dann alles als
  abgerechnet markieren — spätere Nacharbeiten tauchen danach wieder
  unter "Nicht abgerechnet" auf.
- **PDF herunterladen** — Stundennachweis der aktuellen Auswahl (folgt
  beiden Filtern): je Projekt eine Tabelle mit Datum/Von/Bis/Dauer/Notiz
  und Summe, bei mehreren Projekten zusätzlich eine Gesamtsumme. Uhrzeiten
  in der Zeitzone des Browsers. Laufende Zeiterfassungen sind nicht
  enthalten.

### Setup

Firma, Kategorien, Funktionstypen, Zentral-/Allgemeinfunktions-Vorlagen,
Pflichtenheft, Dokumentation, E-Mail, Backup und Zeiterfassung sind eigene Unterreiter
innerhalb des Setup-Tabs, nicht alle gleichzeitig sichtbar. Bei Firma,
Pflichtenheft, Dokumentation, E-Mail, Backup und Zeiterfassung speichert
**Speichern** nur die Felder dieses Unterreiters (mit kurzer Bestätigung
"Gespeichert.") — Änderungen auf einem anderen Unterreiter bleiben davon
unberührt.

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
  Standardtext vorbelegt, siehe Abschnitt *Pflichtenheft* oben) sowie drei
  Kontrollkästchen, die steuern, was im Pflichtenheft-PDF erscheint:
  Vorbemerkungen, Stockwerk-/Raumverzeichnis und Geräteliste (alle
  standardmässig an). Gilt global für alle Projekte, wie der Rest des
  Firmenprofils.
- **Dokumentation** — acht Kontrollkästchen, die steuern, welche
  Abschnitte im Dokumentation-PDF erscheinen (siehe Abschnitt
  *Dokumentation* oben): Funktionscheckliste, Übergabe-Checkliste und
  Handbücher (alle drei standardmässig an), sowie Geräte je Raum,
  Gruppenadressen, Abgangsliste, Verteilerplanung und Klärungsliste (alle
  standardmässig aus, da sie ein Projekt schnell sehr lang machen können
  — gezielt für den Einzelfall dazuschalten). Gilt ebenfalls global für
  alle Projekte.
- **E-Mail** — SMTP-Zugangsdaten (Server, Port, Verschlüsselung
  STARTTLS/SSL/keine, Benutzername/Passwort, Absenderadresse) für den
  **Per E-Mail senden**-Button bei Pflichtenheft, Funktionscheckliste,
  Übergabe-Checkliste, Dokumentation und den offenen Punkten der
  Klärungsliste — rein manuell ausgelöst, nie
  automatisch (z.B. nicht beim Signieren der Übergabe-Checkliste). Ein
  beliebiger SMTP-Account funktioniert (Firmen-Mailaccount, Transaktions-
  E-Mail-Dienst usw.). "Kopie an mich" steuert, ob der Sendedialog
  standardmässig eine Kopie an die oben unter *Firma* hinterlegte
  E-Mail-Adresse vorschlägt. **Test-E-Mail senden** verschickt eine
  Test-Nachricht an eine beliebige Adresse, um die Einstellungen zu
  prüfen, bevor man sich beim eigentlichen Versand darauf verlässt. Beim
  Klick auf **Per E-Mail senden** öffnet sich ein Dialog mit den
  vorausgefüllten Empfängern (aus dem Projekt, siehe *Gruppenadressen*
  oben — **E-Mail** und **Weitere Empfänger** im Projekt-Bearbeiten-
  Formular) sowie einem CC-Feld und optionalem Freitext — erst nach
  **Senden** geht die E-Mail tatsächlich raus, mit dem PDF als Anhang.
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
- **Zeiterfassung** — **Aktiv** schaltet die ganze Zeiterfassung ein
  oder aus (standardmässig an). Ausgeschaltet verschwinden der Tab
  Zeiterfassung und der Start-Knopf im Programmkopf; bereits erfasste
  Zeiten bleiben gespeichert und sind nach dem Wiedereinschalten wieder
  da. **Rundung**: minutengenau, 15 Minuten (Standard) oder 30 Minuten —
  siehe *Zeiterfassung* oben. Eine geänderte Rundung gilt nur für neue
  bzw. neu gespeicherte Einträge; bereits erfasste Zeiten werden nie
  nachträglich umgerechnet, damit schon abgerechnete Summen stabil
  bleiben.

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
Funktionscheckliste, Übergabe-Checkliste, Dokumentation, Offene Punkte der
Klärungsliste, sowie der interne Stundennachweis der Zeiterfassung) nutzen
dieselbe
Gestaltung: ein dunkler
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
