# KNXpilot hinter Authelia auf Synology NAS (Docker/Portainer)

Getestetes Setup: `ghcr.io/seaspotter/knxpilot:latest` (Image-only, kein
Self-Update per `git pull`) + Authelia + nginx als Auth-Frontend, dahinter
Synologys eigener Reverse Proxy für TLS-Terminierung. Variante von
[`DEPLOYMENT.md`](./DEPLOYMENT.md)s Authelia-Abschnitt: dort wird das
gesamte Repository per Bind-Mount eingebunden (Self-Update inklusive) und
`docker compose` direkt aus dem Checkout gestartet; hier läuft nur das
fertige Image über Portainer, ohne `git clone` auf dem NAS.

Alle persistenten Daten liegen unter einem einzigen Ordner auf dem NAS:

```
/volume1/docker/knxpilot_data/
├── data/                       # SQLite-DB (backend/data/knx_ga.db)
└── authelia/
    ├── config/
    │   ├── configuration.yml
    │   ├── users_database.yml
    │   └── secrets/
    │       ├── jwt_secret
    │       ├── session_secret
    │       └── storage_encryption_key
    └── nginx.conf
```

## 1. Voraussetzungen

- Docker + Portainer bereits auf der Synology installiert
- SSH aktiviert (**Systemsteuerung → Terminal & SNMP**)
- Zwei DNS-Subdomains, die auf die NAS zeigen, z.B.
  `knxpilot.deinedomain.tld` und `auth.deinedomain.tld`
- Ein TLS-Zertifikat, das beide Subdomains abdeckt
  (**Systemsteuerung → Sicherheit → Zertifikat**, z.B. Let's Encrypt)

## 2. Ordnerstruktur + Config-Vorlagen holen

```bash
ssh admin@<NAS-IP>

sudo mkdir -p /volume1/docker/knxpilot_data/data
sudo mkdir -p /volume1/docker/knxpilot_data/authelia/config/secrets
cd /volume1/docker/knxpilot_data

sudo curl -fsSL -o authelia/config/configuration.yml \
  https://raw.githubusercontent.com/seaspotter/knxpilot/main/authelia/config/configuration.yml
sudo curl -fsSL -o authelia/config/users_database.yml.example \
  https://raw.githubusercontent.com/seaspotter/knxpilot/main/authelia/config/users_database.yml.example
sudo curl -fsSL -o authelia/nginx.conf \
  https://raw.githubusercontent.com/seaspotter/knxpilot/main/authelia/nginx.conf
```

## 3. Authelia-Geheimnisse erzeugen

```bash
sudo openssl rand -hex 64 | sudo tee authelia/config/secrets/jwt_secret
sudo openssl rand -hex 64 | sudo tee authelia/config/secrets/session_secret
sudo openssl rand -hex 64 | sudo tee authelia/config/secrets/storage_encryption_key
```

## 4. Benutzer anlegen

```bash
sudo cp authelia/config/users_database.yml.example authelia/config/users_database.yml
sudo docker run --rm authelia/authelia:latest \
  authelia crypto hash generate argon2 --password 'DEIN-PASSWORT'
```

Den ausgegebenen `$argon2id$...`-Hash eintragen:

```bash
sudo vi authelia/config/users_database.yml
```

## 5. `configuration.yml` anpassen

Jedes `example.com` / `knxpilot.example.com` / `auth.example.com` durch die
echte Domain ersetzen → betroffen sind `totp.issuer`, die
`access_control`-Regel-Domain sowie `session.cookies[0]` (`domain`,
`authelia_url`, `default_redirection_url`).

⚠️ **Häufigster Fehler:** fehlendes schließendes `'` bei einem der drei
Werte in `session.cookies[0]` → führt zu `yaml: line 43: did not find
expected key` und Authelia startet gar nicht. Nach dem Editieren prüfen:

```bash
sudo cat -A authelia/config/configuration.yml | sed -n '38,47p'
```

Keine `^I` (Tabs) und jede Zeile muss mit `'$` enden, nicht offen bleiben.

## 6. `nginx.conf` anpassen → Domain

```bash
sudo vi authelia/nginx.conf
```

`auth.example.com` → echte Domain ersetzen. Sonst ist an dieser Datei
nichts zu tun: sie setzt das Scheme fest auf `https`, statt es dynamisch
aus der eingehenden Verbindung zu übernehmen (`$scheme`) - Synologys
Reverse Proxy terminiert TLS selbst und leitet intern nur per **HTTP**
an `nginx-front` weiter, `$scheme` wäre hier also immer `http`, und
Authelia lehnt `http`-Session-Cookies dann mit *"insecure scheme"* ab.
(Frühere Versionen dieser Datei nutzten noch `$scheme` - falls Ihre Kopie
älter ist: `grep '\$scheme' authelia/nginx.conf` sollte nichts mehr
finden. Falls doch, jede Fundstelle durch `https` ersetzen.)

## 7. Compose-Datei

Den folgenden Inhalt zusätzlich als `docker-compose.portainer.yml` im
selben Ordner speichern (`sudo vi docker-compose.portainer.yml`) - wird
für die CLI-Update-Variante in Schritt 10 gebraucht, Portainer selbst
braucht nur den Web-Editor-Inhalt:

```yaml
services:
  knxpilot:
    image: ghcr.io/seaspotter/knxpilot:latest
    container_name: knxpilot
    restart: unless-stopped
    expose:
      - "8000"
    volumes:
      - /volume1/docker/knxpilot_data/data:/app/backend/data
      # Optional: NAS-Ziel fürs Setup -> Backup-Feature:
      # - /volume1/docker/knxpilot_data/backups:/app/backups

  authelia:
    image: authelia/authelia:latest
    container_name: knxpilot-authelia
    restart: unless-stopped
    ports:
      # WICHTIG: publiziert (nicht nur "expose"), sonst kann Synologys
      # Reverse Proxy (läuft auf dem Host, nicht im Docker-Netz) den
      # Container nicht erreichen -> DSM-eigene 404-Seite statt Login.
      - "9091:9091"
    volumes:
      - /volume1/docker/knxpilot_data/authelia/config:/config
    environment:
      AUTHELIA_JWT_SECRET_FILE: /config/secrets/jwt_secret
      AUTHELIA_SESSION_SECRET_FILE: /config/secrets/session_secret
      AUTHELIA_STORAGE_ENCRYPTION_KEY_FILE: /config/secrets/storage_encryption_key

  nginx-front:
    image: nginx:alpine
    container_name: knxpilot-nginx-front
    restart: unless-stopped
    depends_on:
      - knxpilot
      - authelia
    volumes:
      - /volume1/docker/knxpilot_data/authelia/nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "8080:80"
```

**Portainer → Stacks → Add stack → Web editor**, obigen Inhalt einfügen,
**Deploy the stack**.

## 8. Synology Reverse Proxy

**Systemsteuerung → Anmeldeportal → Erweitert → Reverse-Proxy → Erstellen**,
zwei Regeln:

| Quelle (HTTPS, Port 443) | Ziel (HTTP) |
|---|---|
| `knxpilot.deinedomain.tld` | `localhost` : 8080 |
| `auth.deinedomain.tld` | `localhost` : 9091 |

## 9. Erster Login

`knxpilot.deinedomain.tld` aufrufen → Redirect zu `auth.deinedomain.tld`.
TOTP-QR-Code kommt nicht per Mail (kein SMTP konfiguriert), sondern landet
in einer Datei:

```bash
sudo docker exec knxpilot-authelia cat /config/notification.txt
```

Link öffnen → QR-Code scannen → fertig, Redirect zurück zu KNXpilot.

## 10. Updates

Kein In-App-Update-Button in dieser Variante (kein `.git`-Mount, siehe
`DEPLOYMENT.md`, Abschnitt "Betrieb ohne Bind-Mount"). Stattdessen:

```bash
cd /volume1/docker/knxpilot_data
sudo docker compose -f docker-compose.portainer.yml pull
sudo docker compose -f docker-compose.portainer.yml up -d
```

oder in Portainer: **Stacks → knxpilot → Pull and redeploy**.

## Troubleshooting-Checkliste

| Symptom | Ursache |
|---|---|
| Authelia-Log: `yaml: line N: did not find expected key` | fehlendes `'` oder falsche Einrückung in `configuration.yml` |
| Authelia-Log: `insecure scheme 'http'` | `nginx.conf` ist eine ältere Kopie, die noch `$scheme` statt `https` nutzt (Schritt 6) |
| `auth.*`-Domain zeigt DSM-eigene 404 | `authelia`-Container nur `expose`, nicht `ports` publiziert, oder Reverse-Proxy-Regel fehlt/falscher Port |
| nginx-front-Log: `connect() failed ... Host is unreachable` auf `:9091` | Authelia-Container crash-loopt (siehe YAML-Fehler oben) → Ursache liegt bei Authelia, nicht bei nginx |
