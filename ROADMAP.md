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
- [ ] **Mobile/tablet-optimized UI, remaining tabs** — the on-site-usable
  tabs (Klärungsliste, Geräteplanung/Abgangsliste quick-add) got a mobile
  pass: stacked full-width fields, bigger touch targets, viewport-capped
  tooltips - see `CHANGELOG.md`. Not yet covered: Setup/Geräte-Katalog
  (not realistically used from a phone, lower priority) and wide data
  displays (Gruppenadressen tree, Verteilerplanung's row layout, various
  tables) which may need horizontal-scroll wrappers or a different
  narrow-viewport presentation rather than the stacked-fields approach
  used for forms.
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
