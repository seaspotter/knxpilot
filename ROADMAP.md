# Roadmap

Working list of ideas for KNXpilot beyond what's already shipped — see
[`CHANGELOG.md`](./CHANGELOG.md) for what's actually been built, release by
release. This file is where "we should do X" goes before it's scoped or
built. Items are removed once they've landed and have a CHANGELOG entry of
their own — keep it current rather than letting it drift into a wishlist
nobody trusts.

## Good ideas, not yet sequenced

- [ ] **.knxproj / ETS import** — parse an existing ETS project export (a
  zip of XML) to pre-populate a KNXpilot project's group addresses, instead
  of always starting from a blank building. High value, but real work
  against ETS's file format.
- [ ] **Auto-fetch device manuals/documentation** — once a project's
  actual devices are known (Geräteplanung/Abgangsliste), automatically
  find/attach the manufacturer's manual or datasheet instead of the
  system integrator tracking them down manually - would back the
  Übergabe-Checkliste's "Bedienungsanleitungen übergeben" item. Needs a
  source (manufacturer sites don't have a uniform API/URL scheme) - likely
  starts as a manually-curated link per `actor_types` entry rather than
  live fetching.
- [ ] **Store project credentials (Passwörter)** — a place to record the
  ETS project password, visualization/app login, router Wi-Fi credentials
  etc. per project, so handover can include them instead of tracking them
  separately - would back the Übergabe-Checkliste's "Passwörter übergeben"
  item. Security-sensitive: needs real thought on encryption at rest before
  building, not just a plain-text column - this isn't a "just add a field"
  task.
- [ ] **Send documentation by email (SMTP)** — send the Dokumentation/
  Übergabe-Checkliste PDF (and other exports) directly to the customer from
  inside KNXpilot instead of downloading and attaching it manually. Needs
  an SMTP config in Setup (mirroring the existing Nextcloud/backup
  credential pattern) and a "send" action next to the existing PDF
  downloads.

## Explicitly deferred

- **In-app user accounts / Benutzerverwaltung** — not planned unless the
  user base actually grows beyond one system integrator. If KNXpilot needs
  to be reachable outside a LAN, the recommended approach is
  infrastructure-level access control in front of the app, not an in-app
  login system — the app has no per-user data model today (single shared
  SQLite DB, no user table), so in-app accounts would only ever be "one
  shared door lock," not real multi-user permissions. `docker-compose.authelia.yml`
  (see `CHANGELOG.md`/`DEPLOYMENT.md`) now covers the reverse-proxy/domain
  case; a plain VPN (WireGuard/Tailscale) remains the simpler option when
  a domain isn't actually needed.
