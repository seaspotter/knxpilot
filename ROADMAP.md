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
- [ ] **Mobile/tablet-optimized UI** — the app is usable on a phone today
  (the subnav already scrolls/wraps) but isn't really optimized for it,
  e.g. adding a Klärungsliste entry on-site during a customer conversation
  is more fiddly than it should be on a small screen. Would need a pass
  over form layouts, touch target sizes, and table/card handling on
  narrow viewports across tabs, not just the nav.
- [ ] **Keep PDF section headings with their first table/paragraph** — in
  some exports a section's heading has landed at the bottom of one page
  with its actual content (e.g. a table) starting on the next, instead of
  moving the heading down onto the same page as its content. ReportLab
  supports `KeepTogether` (wraps flowables so they break as a unit) - needs
  a pass across the shared PDF story-builders (`pdf_design.py` and the
  various `build_*_story` functions) to wrap each heading with at least
  its first following flowable.
- [ ] **File attachments per project** — store a handful of files per
  project (building drawings, manuals, an ETS export) alongside the rest
  of the project data. Deliberately scoped to "a few files," not a general
  document library - see `CHANGELOG.md`/git history for why this was
  previously deferred; revisit with that scope in mind rather than
  building a full attachment/versioning system.
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
  infrastructure-level access control in front of the app, not an in-app
  login system — the app has no per-user data model today (single shared
  SQLite DB, no user table), so in-app accounts would only ever be "one
  shared door lock," not real multi-user permissions. `docker-compose.authelia.yml`
  (see `CHANGELOG.md`/`DEPLOYMENT.md`) now covers the reverse-proxy/domain
  case; a plain VPN (WireGuard/Tailscale) remains the simpler option when
  a domain isn't actually needed.
