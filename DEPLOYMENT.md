# Deployment

KNXpilot is a single Docker Compose service, running a prebuilt image from
`ghcr.io/seaspotter/knxpilot` (published by
[`.github/workflows/docker-publish.yml`](./.github/workflows/docker-publish.yml)
on every push to `main`, as a multi-arch manifest covering `linux/amd64`
and `linux/arm64` — `docker compose pull` picks the right one for the host
automatically, no extra flags needed on a Raspberry Pi or other ARM
server). Code updates apply themselves via `git pull` at runtime (see
below); only a changed `requirements.txt`/`Dockerfile` needs a fresh
`docker compose pull`.

## Persistenz

Projekte liegen in der SQLite-Datei `backend/data/knx_ga.db`, die über
`docker-compose.yml` in den Container eingebunden wird — sie übersteht also
Container-Neubauten/-Neustarts, solange dieser Ordner nicht gelöscht wird.
Die JSON-Sicherung/-Wiederherstellung (siehe README, Abschnitt
Gruppenadressen) ist für explizite Portabilität gedacht (Projekt zwischen
Installationen umziehen, manuelles Backup), nicht für die normale
Persistenz im Alltag nötig.

## Backups (Setup → Backup)

Für den Fall eines Server-/Festplattenausfalls: **Setup → Backup** sichert
die komplette `knxpilot_backup_<Zeitstempel>.db`-Datei (alle Projekte,
Geräte-Katalog, Setup — nicht nur ein einzelnes Projekt wie die
JSON-Sicherung oben) automatisch und/oder auf Knopfdruck auf ein NAS/
gemountetes Verzeichnis und/oder Nextcloud. Beide Ziele sind unabhängig
voneinander aktivierbar; eine Aufbewahrungsanzahl (je Ziel getrennt)
löscht ältere Sicherungen automatisch.

Für das NAS-Ziel muss der Zielordner als Docker-Volume eingebunden sein —
in `docker-compose.yml` ist dafür eine Beispielzeile vorbereitet:
```yaml
- /mnt/nas/knxpilot-backups:/app/backups
```
Der in Setup → Backup eingetragene Pfad (`backup_local_path`) muss dabei
dem Pfad **rechts** vom Doppelpunkt entsprechen (hier `/app/backups`), da
dieser Pfad *innerhalb* des Containers gemeint ist, nicht der Host-Pfad
links davon.

Für das Nextcloud-Ziel: die WebDAV-Ordner-URL (z.B.
`https://cloud.example.com/remote.php/dav/files/BENUTZER/Backups/
KNXpilot/`), Benutzername und ein
[App-Passwort](https://docs.nextcloud.com/server/latest/user_manual/en/session_management.html#managing-devices)
statt des echten Kontopassworts eintragen — lässt sich bei Bedarf einzeln
widerrufen.

**Wiederherstellen läuft direkt in der App**, kein Server-/Dateizugriff
nötig: im Bereich **Vorhandene Sicherungen** (nur für das NAS-Ziel gelistet)
auf **Wiederherstellen** klicken, oder eine Sicherungsdatei (z.B. aus
Nextcloud heruntergeladen) unter **Sicherung wiederherstellen (Datei
hochladen)** hochladen. Beides ersetzt die komplette laufende Datenbank
und startet die App danach automatisch neu — vorher wird immer zuerst
automatisch eine Sicherung des *aktuellen* Stands angelegt (Dateiname
`knxpilot_backup_prerestore_<Zeitstempel>.db`, direkt neben
`backend/data/knx_ga.db`), damit ein versehentliches/falsches
Wiederherstellen selbst noch rückgängig zu machen ist. Eine hochgeladene
Datei wird vor der Übernahme geprüft (muss die KNXpilot-Tabellenstruktur
enthalten) — eine falsche/fremde Datei wird abgelehnt, ohne dass etwas
verändert wird.

## Update von einer früheren Version dieses Tools

Das Datenbankschema migriert beim Start automatisch (neue Spalten werden
ergänzt), eine bestehende `knx_ga.db` funktioniert also weiter. Die
*Vorbelegungsdaten* (Punkttypen, Zentralvorlagen, Standard-Gerätekatalog)
werden allerdings nur einmalig eingefügt, wenn die jeweilige Tabelle leer
ist — Korrekturen daran erscheinen also nicht rückwirkend in einer
bestehenden Installation. Solange sich noch keine echten Projektdaten
angesammelt haben, ist der einfachste Weg, `backend/data/knx_ga.db` zu
löschen und neu vorbelegen zu lassen:

```bash
docker compose down
rm backend/data/knx_ga.db
docker compose pull
docker compose up -d
```

Bei bereits gespeicherten echten Projekten: zuerst mit dem
**⭳ Sichern (JSON)**-Button je Projekt sichern, dann die Datenbank löschen,
danach über **⭱ Aus Sicherung wiederherstellen** zurückspielen.

### Wer vor dieser Restrukturierung (`app/` → `backend/` + `frontend/`)
### aktualisiert

Der Bind-Mount in `docker-compose.yml` (`- .:/app`) bindet immer das
**gesamte Repository-Root** in den Container, unabhängig davon, wie die
Verzeichnisse darin heissen — ein `git pull` auf diese Version zieht die
neue `backend/`/`frontend/`-Struktur automatisch mit. Die Datenbank
(`backend/data/knx_ga.db`, vorher `app/data/knx_ga.db`) bleibt dabei
unangetastet, da sie im selben Mount liegt und nur der Pfad relativ zum
Repo-Root sich ändert. Da sich `Dockerfile` in diesem Schritt geändert hat,
zeigt der Update-Button eine Hinweis-Meldung — einmalig
`docker compose pull && docker compose up -d` auf dem Server ausführen.

## Self-Update-Mechanismus (Update-Tab in der App)

Prüft **nur auf Klick** — nichts läuft automatisch im Hintergrund.
**⟲ Nach Updates suchen** zeigt den aktuellen Stand und, falls auf GitHub
eine neuere Version vorliegt, einen **⭱ Update installieren**-Button.

Voraussetzung, einmalig auf dem Server:
```bash
git branch --set-upstream-to=origin/main main
```
Das Repository ist öffentlich, daher funktioniert `git fetch`/`git pull`
anonym — es sind keine Git-Zugangsdaten im Container nötig.

So funktioniert es: `docker-compose.yml` bindet das **gesamte Repository**
in den Container ein (`- .:/app`). Ein `git pull` (ausgeführt vom
Update-Button, innerhalb des Containers gegen dasselbe eingebundene
Verzeichnis) aktualisiert den laufenden Code sofort — ein Prozess-Neustart
übernimmt ihn, ohne dass ein neues Image nötig ist (siehe
`backend/routers/system.py`). Die Datenbank bleibt dabei unangetastet.
Ändern sich `requirements.txt` oder das `Dockerfile`, führt der Button
**keinen** automatischen Neustart durch — stattdessen zeigt er eine
Meldung, dass ein neues Image nötig ist (`docker compose pull && docker
compose up -d`). Das Image dafür baut GitHub Actions bereits bei jedem
Push auf `main` (siehe oben) — auf dem Server ist dafür kein lokaler
Build nötig, nur ein Pull.

Der Browser bekommt die aktualisierten HTML/CSS/JS-Dateien nach einem
Neustart auch **ohne Hard-Refresh** — `backend/main.py` liefert `frontend/`
mit `Cache-Control: no-cache` aus, was den Browser zu einer bedingten
Anfrage (ETag) vor jeder Verwendung einer zwischengespeicherten Kopie
zwingt statt sie blind zu übernehmen; ein normales Neuladen (F5) reicht
also. Ein gewöhnlicher `Cache-Control`-Header hätte hier tagelang zu
scheinbar "kaputten" Updates geführt, weil einzelne JS-Dateien im
Browser-Cache hängen bleiben, obwohl `index.html` schon neu geladen wird.

**Wichtig für zukünftige Änderungen:** Dieser Mechanismus setzt voraus,
dass das Frontend ohne Build-Schritt auskommt (reines HTML/CSS/JS, direkt
von `backend/main.py` als Static Files ausgeliefert). Ein Bundler/Build-Step
(z.B. Vite, Webpack) würde diesen `git pull`-und-Neustart-Ablauf brechen,
da der Container dann entweder Node zum Bauen bräuchte oder committete
`dist/`-Artefakte. Siehe auch [`CLAUDE.md`](./CLAUDE.md).

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

### Betrieb ohne Bind-Mount (z.B. Portainer, reines `docker run`)

Der Selbst-Update-Mechanismus oben setzt zwingend voraus, dass `/app` im
Container ein echter Git-Checkout ist (`- .:/app` in `docker-compose.yml`).
Wird das Image stattdessen direkt gestartet — z.B. in Portainer nur mit
`ghcr.io/seaspotter/knxpilot:latest` und einem Datenvolume, ohne das
gesamte Repository einzubinden — gibt es kein `.git`-Verzeichnis (das
`Dockerfile` kopiert nur `backend/` und `frontend/` ins Image), ein
Update ist dann nur über ein neues `docker pull` des Images möglich.

Das erkennt die App automatisch: fehlt `.git`, blendet sie den
**Update**-Tab komplett aus, statt eine verwirrende rohe Git-Fehlermeldung
zu zeigen — keine Einstellung nötig, funktioniert für beide Varianten von
selbst.

**Bekannte Einschränkung derselben Ursache:** Aus demselben Grund fehlen
in diesem Betriebsmodus auch `CHANGELOG.md` und `MANUAL.md` im Container
(ebenfalls nicht ins Image kopiert) — der **Hilfe**-Tab und die
Änderungsprotokoll-Ansicht im Update-Tab bleiben leer. Für die volle
In-App-Doku (Hilfe/Changelog) und funktionierendes Ein-Klick-Update bleibt
der dokumentierte Bind-Mount-Betrieb (siehe oben, bzw. die Proxmox-Anleitung
unten) die vollständige Variante.

## Bereitstellung auf Proxmox

Ein schlankes LXC mit Docker ist die einfachste Variante:

1. Ein unprivilegiertes Debian/Ubuntu-LXC anlegen (1 vCPU / 512MB–1GB RAM
   reicht).
2. **Nesting** aktivieren (Optionen → Features), damit Docker im LXC
   laufen kann.
3. Docker installieren, direkt aus Ubuntus eigenen Paketquellen (kein
   Fremd-Repository nötig):
   ```bash
   apt update && apt install -y docker.io docker-compose-v2
   ```
   **Wichtig:** Das Paket heisst `docker-compose-v2`, **nicht**
   `docker-compose-plugin` — letzteres ist Dockers eigener Paketname aus
   deren eigenem APT-Repository, nicht aus Ubuntus Repos. `apt install`
   bricht die gesamte Transaktion ab, sobald ein Paketname nicht auflösbar
   ist (dann wird auch `docker.io` NICHT installiert) — daher der korrekte
   Name. `docker-compose-v2` liefert das `docker compose`-Subcommand seit
   Ubuntu 23.10 (mantic) in den Standard-Repos. Danach prüfen:
   `docker --version && docker compose version`.

   Falls `docker-compose-v2` auf Ihrer Distribution fehlt (z.B. ältere
   Debian-Version ohne dieses Paket), alternativ Dockers offizielles
   Installationsskript, das das richtige Fremd-Repository selbst einrichtet:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```
4. Dieses Verzeichnis (per `git clone`) hineinkopieren, hineinwechseln,
   `docker compose pull && docker compose up -d`.
5. `http://<lxc-ip>` aufrufen.

Falls `docker compose pull` mit einem Berechtigungsfehler fehlschlägt: das
GHCR-Package könnte privat sein (Packages erben die Sichtbarkeit eines
öffentlichen Repos nicht automatisch). Prüfen/ändern unter
`github.com/seaspotter?tab=packages` → **knxpilot** → **Package settings**
→ Sichtbarkeit auf **Public** stellen.

## KNXpilot hinter Authelia (Domain-/Reverse-Proxy-Zugriff)

KNXpilot hat bewusst keine eigene Authentifizierung (siehe README) — für
den Betrieb im eigenen internen Netzwerk völlig ausreichend. Soll das Tool
stattdessen über eine Domain erreichbar sein (z.B. über den Reverse Proxy
einer Synology DSM), gehört eine Zugriffskontrolle davor.
`docker-compose.authelia.yml` baut dafür einen alternativen Stack mit
[Authelia](https://www.authelia.com/) (Login mit Passwort + TOTP) und
einem vorgeschalteten nginx, der jede Anfrage erst bei Authelia prüft,
bevor sie zu KNXpilot durchgereicht wird.

**Wichtig:** Diese Datei ersetzt `docker-compose.yml` — nur eine der
beiden Compose-Dateien gleichzeitig verwenden, nicht beide zusammen
starten.

### Aufbau

```
Internet → Synology Reverse Proxy (Domain + TLS-Zertifikat)
             ├─ auth.ihredomain.tld      → authelia:9091 (Login-Portal)
             └─ knxpilot.ihredomain.tld  → nginx-front:8080 → (nach Login) → knxpilot:8000
```

Die Synology übernimmt Domain und TLS-Zertifikat wie gewohnt; intern
laufen zwei zusätzliche Container neben `knxpilot`: `nginx-front` (prüft
jede Anfrage bei Authelia, leitet erst danach zu KNXpilot weiter) und
`authelia` (das eigentliche Login-Portal, inkl. TOTP-Verwaltung).

### Einrichtung

1. Geheimnisse einmalig erzeugen (je Datei ein zufälliger String, landen
   ungetrackt in `authelia/config/secrets/`):
   ```bash
   mkdir -p authelia/config/secrets
   openssl rand -hex 64 > authelia/config/secrets/jwt_secret
   openssl rand -hex 64 > authelia/config/secrets/session_secret
   openssl rand -hex 64 > authelia/config/secrets/storage_encryption_key
   ```
2. Benutzer anlegen: `authelia/config/users_database.yml.example` nach
   `authelia/config/users_database.yml` kopieren, Passwort-Hash erzeugen
   und eintragen (Befehl dafür steht als Kommentar in der Datei).
3. Domain eintragen: in `authelia/config/configuration.yml` und
   `authelia/nginx.conf` alle `example.com` / `knxpilot.example.com` /
   `auth.example.com`-Platzhalter durch die eigene Domain ersetzen — zwei
   Subdomains nötig, eine fürs Login-Portal und eine für KNXpilot selbst
   (siehe Aufbau oben).
4. Stack starten: `docker compose -f docker-compose.authelia.yml up -d`.
5. Auf der Synology (**Systemsteuerung → Anmeldeportal → Erweitert →
   Reverse-Proxy**) zwei Regeln anlegen: `auth.ihredomain.tld` → interne
   IP des Docker-Hosts, Port `9091` (`authelia`); `knxpilot.ihredomain.tld`
   → interne IP des Docker-Hosts, Port `8080` (`nginx-front`) — die
   Container-Namen selbst gelten nur intern zwischen den Containern, die
   Synology braucht IP:Port im LAN.
6. Erster Login: die TOTP-Einrichtung erzeugt einen QR-Code-Link statt
   einer E-Mail (kein SMTP-Server konfiguriert) — direkt danach mit
   `docker compose -f docker-compose.authelia.yml exec authelia cat
   /config/notification.txt` auslesen.

### Bewusste Vereinfachungen

- **Ein Benutzer statt LDAP/OIDC** — Authelia kann deutlich mehr, aber für
  einen einzelnen Systemintegrator reicht die dateibasierte Benutzerliste.
- **Kein SMTP-Server** — Benachrichtigungen (TOTP-Einrichtung,
  Passwort-Reset) landen in einer lokalen Datei statt per E-Mail, siehe
  Schritt 6.
- **SQLite statt Redis/PostgreSQL** — für eine Handvoll Logins völlig
  ausreichend, kein zusätzlicher Dienst nötig.

Diese Konfiguration richtet sich nach Authelias Schema-Stand rund um
Version 4.38 — schlägt der Start nach einem Image-Update fehl, meldet
Authelia in den Logs (`docker compose -f docker-compose.authelia.yml logs
authelia`) meist genau, welcher Konfigurationsschlüssel sich geändert hat;
die [offizielle Doku](https://www.authelia.com/configuration/) ist die
verbindliche Referenz, diese Dateien nur ein Startpunkt.

Reicht stattdessen ein VPN zum eigenen Netzwerk (WireGuard/Tailscale),
ist das oft die einfachere Alternative zu Domain + Reverse Proxy + Login —
kein Setup hier nötig, siehe README.

Das Dateisystem des LXC (inkl. der Datenbank) wird automatisch von den
üblichen Proxmox-Backup-Jobs erfasst.
