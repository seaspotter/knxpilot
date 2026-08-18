# Roadmap

Working list of ideas for KNXpilot beyond what's already shipped — see
[`CHANGELOG.md`](./CHANGELOG.md) for what's actually been built, release by
release. This file is where "we should do X" goes before it's scoped or
built. Check items off (or delete them once they've landed and have a
CHANGELOG entry of their own) as they're done — keep it current rather than
letting it drift into a wishlist nobody trusts.

## Up next

- [x] **Labels** — Avery Zweckform L6037 label sheet export (Abgangsliste
  sub-tab), one label per actor instance or per channel, with a position
  picker to resume a partially-used sheet and a test-print/alignment mode.
  See `CHANGELOG.md` for detail.
- [x] **DIN-Rail / Verteiler (cabinet) layout** — new Verteilerplanung
  sub-tab: fixed 12-TE rows per Geschoss, RCD (4TE)/LS-Schalter (1TE)
  placeholder blocks, and already-placed Abgangsliste actor instances
  (sized by their Geräte-Katalog TE width) all placeable into rows, with
  capacity/uniqueness enforced. See `CHANGELOG.md` for detail. Scoped
  down from an earlier idea of an explicit RCD→LS-Schalter→circuit
  protection hierarchy (each RCD grouping specific LS-Schalter, each
  protecting specific circuits/channels) — user confirmed RCD/LS should
  just be simple labeled blocks for now, not linked to specific circuits.
  That fuller hierarchy is a possible future refinement, not currently
  planned.

## Good ideas, not yet sequenced

- [x] **Automated backups** to a NAS (mounted volume) or Nextcloud (WebDAV) —
  Setup → Backup, see `CHANGELOG.md`. A Google-Drive destination would need
  OAuth2 — meaningfully more work, not built, worth scoping separately if
  actually wanted later.
- [ ] **.knxproj / ETS import** — parse an existing ETS project export (a
  zip of XML) to pre-populate a KNXpilot project's group addresses, instead
  of always starting from a blank building. High value, but real work
  against ETS's file format.
- [x] **All-projects dashboard** — Projektübersicht above the Projekte
  list (status breakdown, open/aged Klärungen, projects without
  structure). See `CHANGELOG.md`.
- [x] **Reminders/aging on Klärungsliste** — 7-day aged badge + digest
  banner + warn-colored sub-tab button. See `CHANGELOG.md`.
- [ ] **Split Pflichtenheft from a future "Finale Dokumentation"** —
  Pflichtenheft today bundles everything (planned functions, device lists,
  Gruppenadressen, Abgangsliste, Verteilerplanung...) behind toggles and
  is used at both ends of a project: as the pre-project spec/scope
  document agreed with the customer, and again informally as an as-built
  record once everything is finished. Those are conceptually different
  moments - "what we agreed to build" vs. "what we actually built" - and
  may want to become two separate documents/exports instead of one
  toggle-everything PDF. Not scoped yet; raised while building the
  Geräte-je-Raum export, which currently lives as just another
  Pflichtenheft toggle.

## Explicitly deferred

- **In-app user accounts / Benutzerverwaltung** — not planned unless the
  user base actually grows beyond one system integrator. If KNXpilot needs
  to be reachable outside a LAN, the recommended approach is
  infrastructure-level access control (WireGuard/Tailscale, or a
  reverse-proxy auth layer like Authelia/Authentik with 2FA) in front of
  the app, not an in-app login system — the app has no per-user data model
  today (single shared SQLite DB, no user table), so in-app accounts would
  only ever be "one shared door lock," not real multi-user permissions.
- **File attachments per project** (site photos, floor plans, ETS exports)
  — not needed right now.
