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
  against ETS's file format. Groundwork: format hypotheses, a proposed
  mapping and open questions in [`docs/FINDINGS-knxproj.md`](./docs/FINDINGS-knxproj.md),
  plus a read-only probe (`tools/knxproj_probe.py`) - **next step: run it
  on 2-3 real ETS exports and verify the hypotheses before writing any
  import code.**
- [ ] **Store project credentials (Passwörter)** — a place to record the
  ETS project password, visualization/app login, router Wi-Fi credentials
  etc. per project, so handover can include them instead of tracking them
  separately - would back the Übergabe-Checkliste's "Passwörter übergeben"
  item. Security-sensitive: needs real thought on encryption at rest before
  building, not just a plain-text column - this isn't a "just add a field"
  task.
- [ ] **Gebäudestruktur as a tree view (ETS-like)** — raised 2026-09-26.
  A compact collapsible tree (Geschoss → Raum → Verteiler) instead of one
  big card per room, with drag & drop to reorder rooms and move a room to
  another Geschoss (native HTML5 drag & drop, no framework needed).
  Proposed steps: (1) tree + drag & drop for rooms/floors; moving a room
  changes its functions' Mittelgruppe, so the drop needs a confirm and the
  GA "Änderungen seit dem letzten ETS-Export" view shows the effect;
  (2) Verteiler optionally placed in a room (today a Verteiler belongs
  only to a Geschoss), useful for the Dokumentation. **Rooms inside rooms**
  is the open question: every export, the GA naming "{Raum} {Label}", the
  checklists and the PA buckets assume exactly Geschoss → Raum, so nesting
  would touch almost everything - only worth it for a concrete use case
  (e.g. "Wohnung → Zimmer"), and then possibly as a grouping level above
  rooms rather than arbitrary nesting.

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
