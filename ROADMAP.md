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
