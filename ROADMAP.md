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
- [ ] **DIN-Rail / Verteiler (cabinet) layout** — given a cabinet's DIN-rail
  rows, RCD/LS Schalter inventory, and available space, generate the
  physical layout: which fuse/RCD group belongs to which circuit, and which
  actor channel goes where in the Verteiler. Builds on Labels above (once a
  circuit has a physical position, its label prints at that position) but
  needs three new pieces: a Verteiler config (rows, module width/TE,
  RCD/LS Schalter inventory), an allocation step (packing channels +
  protective devices into the available space, respecting RCD groupings),
  and a rendered layout diagram. Not yet spec'd in detail — needs its own
  planning pass before starting.

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
