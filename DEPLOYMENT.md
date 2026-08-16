# Deployment

KNXpilot is a single Docker Compose service, running a prebuilt image from
`ghcr.io/seaspotter/knxpilot` (published by
[`.github/workflows/docker-publish.yml`](./.github/workflows/docker-publish.yml)
on every push to `main`). Code updates apply themselves via `git pull` at
runtime (see below); only a changed `requirements.txt`/`Dockerfile` needs a
fresh `docker compose pull`.

## Persistenz

Projekte liegen in der SQLite-Datei `backend/data/knx_ga.db`, die über
`docker-compose.yml` in den Container eingebunden wird — sie übersteht also
Container-Neubauten/-Neustarts, solange dieser Ordner nicht gelöscht wird.
Die JSON-Sicherung/-Wiederherstellung (siehe README, Abschnitt
Gruppenadressen) ist für explizite Portabilität gedacht (Projekt zwischen
Installationen umziehen, manuelles Backup), nicht für die normale
Persistenz im Alltag nötig.

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
GHCR-Package ist beim allerersten Build evtl. noch privat. Einmalig unter
`github.com/seaspotter?tab=packages` → **knxpilot** → **Package settings**
→ Sichtbarkeit auf **Public** stellen (das Repository selbst ist bereits
öffentlich, das Package erbt das nicht automatisch).

Das Dateisystem des LXC (inkl. der Datenbank) wird automatisch von den
üblichen Proxmox-Backup-Jobs erfasst.
