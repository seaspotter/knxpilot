# Changelog

Notable changes to KNXpilot. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/); this file starts from the
restructuring below — history before that is available via `git log`.

## [0.5.0] - 2026-08-18

### Added

- Mobile/tablet-optimized data entry across the whole app, not just the
  on-site-usable tabs from the previous pass: every genuine multi-field
  form row now stacks each field onto its own full-width line below
  700px instead of wrapping several fixed-width fields into a cramped
  multi-column jumble - Funktionen's room-function quick-add, the
  Geräte-Katalog add-device form, Gebäudestruktur, Setup (Firma,
  Funktionstypen, Zentral-/Allgemeinfunktions-Vorlagen, Backup), project
  create/rename/meta-edit modals, Verteilerplanung's "Verteiler anlegen",
  and more - via an opt-in `.mobile-fields` class, not applied to every
  `.row` (most are button toolbars that already wrap fine as-is). Several
  inline `style="width:…"`/`style="min-width:…; flex:1"` attributes were
  converted to shared width classes (`.w-60`/`.w-110`/.../`.w-220`,
  `.flex-input`, `.flex-input-wide`) along the way, since a mobile media
  query can't override an inline style without `!important`.
  Verteilerplanung's DIN-rail row diagram (percentage-width boxes that
  became illegible, though not page-overflowing, once squeezed onto a
  narrow screen) gets a horizontal-scroll wrapper with a legible minimum
  width instead of being force-stacked like a form. Also: bigger touch
  targets app-wide below 700px (buttons, inputs/selects incl. 16px font
  to avoid iOS Safari's auto-zoom-on-focus, icon buttons, inline pill
  edit/delete links), info-icon/icon-button tooltips capped to the
  viewport width, and a fix for the Update/Hilfe tabs' markdown-rendered
  `<pre><code>` blocks (e.g. the CSV column list in the manual) causing
  page-level horizontal overflow despite their own `overflow-x:auto`.
  Verified via CDP at a 375px viewport across all 19 tabs/subtabs -
  zero horizontal overflow anywhere - and confirmed desktop (1400px) is
  visually unchanged.

### Fixed

- PDF exports no longer strand a section heading alone at the bottom of a
  page with its table/content starting on the next one - every
  `SectionHeading`/`RoomHeading` across the shared PDF story-builders
  (Geräteliste, Geräte je Raum, Verteilerplanung, Abgangsliste,
  Pflichtenheft incl. Gruppenadressen, Übergabe-Checkliste) is now wrapped
  with at least its first following flowable in a ReportLab `KeepTogether`
  group. Safe for long tables too - `KeepTogether` only forces a
  fresh-page start for the group, it doesn't stop a long table from
  paginating normally afterwards (verified against a 200-row table).
- The header version badge now shows something meaningful in a plain-image
  deployment too (Portainer, bare `docker run`, no `docker-compose.yml`
  bind-mount) instead of going blank - `GET /api/system/version` fell back
  to `None` whenever there was no live `.git` checkout to `git describe`.
  The version is now baked into the image at build time (`KNXPILOT_IMAGE_VERSION`,
  set via `--build-arg` in `.github/workflows/docker-publish.yml`, which
  now also fetches full tag history to compute it) and used as a fallback
  only when the live git describe isn't available.

### Added

- New [`DEPLOYMENT-authelia-synology-portainer.md`](./DEPLOYMENT-authelia-synology-portainer.md) -
  a tested, standalone walkthrough for running KNXpilot behind Authelia
  on a Synology NAS via Portainer (image-only, no git checkout on the
  server), including the Synology reverse-proxy configuration and a
  troubleshooting table for the real issues hit along the way.

### Fixed

- `authelia/nginx.conf` hardcodes the forwarded scheme to `https` instead
  of reflecting the incoming connection's own scheme (`$scheme`) - this
  front proxy only makes sense behind a TLS-terminating edge reverse
  proxy, and most of those (Synology's DSM reverse proxy included)
  forward internally over plain HTTP after terminating TLS themselves, so
  `$scheme` evaluated to `http` and Authelia rejected the session cookie
  as an "insecure scheme". Found via real-world testing behind a Synology
  reverse proxy.
- `docker-compose.authelia.yml`'s `authelia` service now publishes port
  9091 (`ports`) instead of only `expose`-ing it - an edge reverse proxy
  (Synology's included) runs on the host, not inside the compose network,
  so it could never actually reach the login portal with `expose` alone;
  the `auth.*` subdomain would 404 instead of showing the Authelia login.
- `Dockerfile` now also copies `CHANGELOG.md`/`MANUAL.md` into the image -
  previously only `backend/`/`frontend/` were included, so the **Hilfe**
  tab and the Update tab's changelog viewer came up empty when running
  the plain image directly (e.g. Portainer) instead of the documented
  `docker-compose.yml` bind-mount deployment. Unlike self-update (which
  genuinely needs a real git checkout), these are just static files, so
  this fixes it properly rather than hiding the tab.

## [0.4.1] - 2026-08-18

### Added

- The **Update** tab now auto-hides when `/app` isn't a real git checkout
  (e.g. running the plain `ghcr.io/seaspotter/knxpilot` image directly -
  in Portainer or a bare `docker run` - instead of the documented
  `docker-compose.yml` bind-mount deployment) - previously it showed a
  confusing raw git error, since self-update can never work without the
  repo mounted in. No configuration needed, detected automatically. New
  `self_update_available` field on `GET /api/system/version`. See
  `DEPLOYMENT.md`, section "Betrieb ohne Bind-Mount" for the same
  deployment mode's related Hilfe/Changelog limitation.

## [0.4.0] - 2026-08-18

### Added

- New `docker-compose.authelia.yml` - an alternative deployment stack
  fronting KNXpilot with [Authelia](https://www.authelia.com/) (password +
  TOTP login) behind an nginx forward-auth proxy, for setups that expose
  KNXpilot via a domain/reverse proxy (e.g. a Synology DSM reverse proxy)
  instead of only within the LAN. See `DEPLOYMENT.md`, section "KNXpilot
  hinter Authelia".
- New **Geräte je Raum** PDF export (Geräteplanung → PDF herunterladen in
  that section) - every device in the project (room devices, floor
  devices, and Abgangsliste's actor instances) grouped by Geschoss/Raum
  with Gruppe, Hersteller, Typ and physische Adresse, as an installation
  reference distinct from the order-focused Geräteliste export. Also
  available as an optional Pflichtenheft section (new
  "Geräte je Raum"-Kontrollkästchen in Setup → Pflichtenheft, same pattern
  as the existing Abgangsliste/Verteilerplanung sections there). New
  `GET /api/projects/{id}/export-geraete-je-raum.pdf`, new
  `pflichtenheft_include_geraete_je_raum` company-profile column.
- Geräteplanung devices can now attach directly to a **Geschoss** instead
  of always requiring a room - for devices that don't belong to any
  particular room, e.g. a Wetterstation on the facade or an outdoor
  Bewegungsmelder. New "Geräte ohne Raum" section per floor, same
  add/edit/quantity/address behavior as room devices (including working
  with PA automatisch zuordnen and Nicht bestellen). New `floor_devices`
  table (sibling to `room_devices` rather than an in-place migration),
  new `GET/POST /api/floors/{id}/devices`,
  `PUT/DELETE /api/floor-devices/{id}`.
- Geräteplanung's Stückliste entries can be marked **Nicht bestellen**
  (per project, per device type) for devices already on hand - e.g. a
  spare Wetterstation or Tor-Aktor left over from another job. Stays
  visible in the Stückliste (with a "Bereits vorhanden" note) but drops
  out of the Geräteliste PDF's order table, listed separately underneath
  instead. New `device_order_flags` table, new
  `PUT /api/projects/{id}/device-order-flags/{device_type_id}`.
- Geräteliste PDF (Setup → Geräteplanung → PDF herunterladen) reworked:
  Hersteller and Typ are now separate table columns (previously combined
  into one "Gerät" column), and the per-room "Verteilung je Raum" section
  is gone - this export is meant as a clean order list for a supplier,
  not a room-by-room breakdown (that's what Pflichtenheft's own device
  listing is for).
- Geräteplanung entries are now **per-instance** instead of quantity-
  aggregated (one row was "N× DeviceType"; now each physical device is its
  own row) so each can carry its own **physische Adresse**, the way
  Abgangsliste's actor instances already could - non-Aktor bus devices
  (Sensoren, Bedienelemente, Wetterstationen) need an individual KNX
  address too, not just actuators. "Anzahl" in the quick-add form now
  means "how many independent rows to create at once"; each is editable
  (note + address) via a new **Bearbeiten** link. One-time, idempotent
  migration splits any pre-existing aggregated row into that many
  quantity=1 rows - no data lost. New `PUT /api/room-devices/{id}`. The
  quick-add form itself now also takes a physical address directly when
  adding exactly one device at once (disabled for bulk-adds of more than
  one, since a single typed-in address can't be distributed across
  several new rows).
- **PA automatisch zuordnen** (Abgangsliste and Geräteplanung, both act
  project-wide across both tabs) fills in physical KNX addresses for
  every device without one, following a fixed convention: a Systemgeräte
  block (0-5), then one Aktoren block per Geschoss, then one Sensoren/
  Bedienelemente block per Geschoss, then an Aussen block (any Geschoss
  marked Aussen/unbeheizt, Wetterstation devices first) - each block
  starts at the next multiple of 10 and reserves as many full decades as
  its actual device count needs, so later additions don't collide with
  the next block. Never overwrites an address already set; devices with
  no Geschoss are skipped and reported. Area.line prefix (default `1.1`)
  is editable per run. New `backend/pa_assign.py`, new
  `POST /api/projects/{id}/assign-physical-addresses`.
- Geräteplanung's **Stückliste** (project-wide bill of materials, both the
  in-app total and the Geräteliste PDF's per-room breakdown) now also
  counts actor instances placed via the Abgangsliste tab - previously
  those only counted if separately re-entered as a `room_devices` planning
  entry too, so the "total" undercounted anything only wired via
  Abgangsliste. The Übersicht dashboard's Geräteplanung card total updates
  accordingly, since it already reads from the same endpoint. New
  `_actor_instance_room_rows()` helper factors the merge for the PDF's
  per-room section, grouped by Standortbezeichnung (Abgangsliste actor
  instances don't have a `room_id`, only a floor + free-text location).
  The **Aktor** group is no longer offered in Geräteplanung's device
  picker either - now that Abgangsliste actors already count toward the
  same Stückliste, entering an Aktor here too would just be a second,
  redundant (and easy to lose track of) way to log the same kind of
  device, with none of Abgangsliste's floor/address/channel tracking.
- **Übersicht** gets a Verteilerplanung card ("N Verteiler angelegt"),
  matching the one-card-per-sub-tab pattern already used for the others
  (Labels still excluded - no natural short summary for it).
- Abgangsliste: actor instances can now be **edited** (Geschoss,
  Standortbezeichnung, physische Adresse) after being created — e.g. add
  actors first and fill in the physical address later, once known. The
  actor type itself isn't editable this way (delete and re-add instead),
  since a different channel type/count could orphan already-assigned
  Abgänge. New `PUT /api/actor-instances/{id}`.
- **Verteilerplanung** — new project sub-tab: a simple visual DIN-rail
  cabinet layout per Geschoss. A Verteiler has a fixed number of 12-TE
  rows; each row holds RCD/LS-Schalter blocks (simple labeled/sized
  placeholders, default 4TE/1TE, no link to specific circuits yet - see
  `ROADMAP.md`) and/or actor instances already placed via the
  Abgangsliste tab, sized from their Geräte-Katalog TE width (a device
  without a TE width set can't be placed, and the device picker shows
  each candidate's TE alongside its address). Rows enforce the 12 TE
  capacity and a device can only be placed once across all Verteiler in
  a project. New `verteiler`/`verteiler_items` tables, new
  `backend/routers/verteiler.py`.
- Verteilerplanung: **PDF herunterladen** exports every Verteiler in the
  project as one document - one proportionally-sized row table per DIN-
  rail row, matching the on-screen layout. Can also be optionally
  included in the Pflichtenheft PDF (new checkbox in Setup →
  Pflichtenheft, same on/off pattern as Abgangsliste/Gruppenadressen/
  Klärungsliste). New `GET /api/projects/{id}/export-verteilerplanung.pdf`,
  new `company_profile.pflichtenheft_include_verteilerplanung` column.
- Geräte-Katalog entries can now record a **TE** (Teilungseinheiten, DIN-
  rail width - 1 TE = 18mm) alongside Type/Kanäle. Optional, blank unless
  known - only meaningful for rail-mounted devices. First piece of the
  still-unbuilt DIN-Rail/Verteiler layout roadmap item (`ROADMAP.md`):
  capturing device widths now, independent of the bigger allocation/
  layout work that builds on it later. New `actor_types.width_te`
  column, included in export/import JSON.
- The seeded starter catalog now includes real datasheet TE widths for
  most rail-mounted devices (MDT, Phoenix Contact, Gira, Enertex - fed
  in by the user), plus 14 previously-uncatalogued devices found along
  the way (two more MDT Jalousieaktoren with Fahrtzeitmessung, nine
  Enertex system/power-supply/dimmer devices, three Theben presence/
  motion sensors).
- The starter catalog is no longer a hardcoded Python list - a fresh
  install now seeds directly from the bundled `docs/templates/
  geraete-katalog_<hersteller>.json` files (one per manufacturer:
  `_mdt`, `_bj`, `_phoenix`, `_elsner`, `_theben`, `_gira`, `_enertex`,
  `_hoermann`), the same files also offered as downloadable templates -
  a new manufacturer file just needs to follow the naming pattern to be
  picked up, no code change. New **⟲ Standard-Katalog importieren**
  button (Geräte-Katalog tab) re-runs that same import on demand later
  (e.g. to pick up newly-added default devices) - deliberately **not**
  automatic on every restart like an earlier version of this change did,
  since a device someone intentionally deleted shouldn't silently
  reappear. New `POST /api/actor-types/import-defaults`.
- **Projektübersicht** — a status dashboard above the Projekte list,
  summarizing every project at once: total count with clickable
  per-status badges (click sets the search field to that status),
  open Klärungen total (with an "aged" sub-count — see below — and each
  affected project listed, clicking jumps straight into its
  Klärungsliste), and projects with no floors defined yet (each
  clicking straight into Gebäudestruktur). New `GET /api/projects/
  dashboard`, computed with a handful of aggregate SQL queries rather
  than one call per project.
- **Aging on Klärungsliste**: an open entry unanswered for more than 7
  days is now flagged - an "N Tage offen" badge on the entry itself, the
  sub-tab button turns warn-colored, and a summary line appears above
  the list ("⚠ N Einträge sind seit mehr als 7 Tagen unbeantwortet").
  The same 7-day threshold and aged-count feed the new Projektübersicht
  above. `GET /projects/{id}/klaerungen` now includes `age_days`/`aged`
  per entry (computed in SQL via `julianday()`, not client-side, to
  avoid timezone-parsing ambiguity). New shared `AGED_KLAERUNG_DAYS`
  constant in `backend/utils.py`.

### Changed

- **Alle automatisch zuordnen** (Abgangsliste) now prefers aligned channel
  pairs (A+B, C+D, E+F, G+H) for Rollo/Jalousie circuits: when 2+
  unassigned circuits from the same room land on the same actuator, they
  get placed on a shared pair instead of whatever two channels happen to
  be next free — many shading actuators share a common input/reference
  per channel pair (e.g. for Fahrtzeitmessung), so this now matches real
  wiring instead of just filling channels in document order. Every other
  channel type keeps its previous first-free-channel behavior unchanged.
  `get_circuits()` (`backend/ga_logic.py`) now also returns `room_id` per
  circuit (additive, used for the grouping).

### Fixed

- `GET /api/projects/{id}/actor-instances` crashed with a 500 if any
  actor instance's device type had no `channel_count` (i.e. any group
  other than Aktor) - `dict.get(key, default)` only falls back when the
  key is *missing*, not when its value is `None`, and `actor_types`
  always has the column, just `NULL` for non-Aktor groups. Only surfaced
  once non-Aktor devices could plausibly end up referenced from this
  table (surfaced while testing PA auto-assign's Systemgeräte bucket).
- The project workspace's sub-tab row (now 10 tabs after this session's
  additions) could run out of room and misalign the active-tab underline
  against the row's bottom border. `.subnav` now wraps onto a second row
  on narrow-ish desktop widths instead of cramming everything onto one
  line - mobile keeps its existing horizontal-scroll behavior unchanged
  (that media query already overrides wrapping back off).

## [0.3.1] - 2026-08-16

### Fixed

- Listing/pruning existing Nextcloud backups (used by Setup → Backup's
  "Vorhandene Sicherungen" list and by retention pruning after each
  upload) sent a body-less `PROPFIND` request, which several real WebDAV
  servers - Nextcloud's SabreDAV included - reject or mishandle even
  though the WebDAV RFC technically allows omitting the body. This made
  a perfectly successful backup **upload** get reported as a failure,
  because the retention step run right after it would throw. Now sends a
  proper request body/`Content-Type`, and a listing/pruning failure is
  logged but no longer turns an already-successful upload into a
  reported failure.

### Added

- **Setup → Backup**'s "Vorhandene Sicherungen" now lists Nextcloud
  backups too (previously local-only), each with its own Herunterladen/
  Wiederherstellen, and a Nextcloud listing error (e.g. wrong URL/
  credentials) is shown without hiding an otherwise-working local list.
  New `GET /api/system/backups/nextcloud/{filename}/download` and
  `POST /api/system/restore-nextcloud/{filename}`.

## [0.3.0] - 2026-08-16

### Added

- A new **Setup → Backup** sub-tab: automatic and/or manual (**Jetzt
  sichern**) backups of the whole database (not just one project - a
  complete, atomic snapshot via SQLite's own `.backup()` API) to a NAS/
  mounted folder and/or Nextcloud (WebDAV), independently toggleable,
  each with its own retention count (oldest backups beyond it are pruned
  automatically). Automatic backups run from a lightweight in-process
  background task (checks every 15 min whether the configured interval
  has elapsed) - no external scheduler/cron needed, though the manual
  button plus `POST /api/system/backup` work fine for a host-cron setup
  too, if preferred. Nextcloud upload uses plain WebDAV over the standard
  library (`urllib`) - no new dependency for that part. New
  `backend/backup.py`, 11 new `company_profile` columns, see
  `DEPLOYMENT.md` for the NAS bind-mount and Nextcloud app-password
  setup.
- **Restoring now happens in the app itself**, not just by hand: **Setup
  → Backup**'s "Vorhandene Sicherungen" lists every backup in the NAS/
  mounted destination (with per-file Herunterladen/Wiederherstellen), and
  "Sicherung wiederherstellen (Datei hochladen)" restores from any
  uploaded `.db` file (e.g. downloaded from Nextcloud). Either path
  validates the file actually looks like a KNXpilot database first
  (rejects anything else with a clear error, nothing touched), always
  takes a `knxpilot_backup_prerestore_<timestamp>.db` safety snapshot of
  the *current* database before overwriting it (so a wrong/accidental
  restore is itself still recoverable), then restarts the app the same
  way the self-update flow does. New `GET /api/system/backups`,
  `GET /api/system/backups/{filename}/download`,
  `POST /api/system/restore-local/{filename}`,
  `POST /api/system/restore-upload`. **New dependency:
  `python-multipart`** (required by FastAPI for file-upload form
  parsing) - this release needs `docker compose pull && docker compose
  up -d` (not just a self-update restart) to pick it up.
- A new **Labels** project sub-tab (next to Abgangsliste, whose actor/
  channel data it reuses): prints a label sheet for the Schaltschrank —
  one label per actor instance (physical address + location) or per
  channel (physical address + channel letter, plus the assigned
  function/`RESERVE`), with a clickable position picker to resume a
  partially-used sheet instead of starting over, and a debug/test-print
  mode (border + position number) for checking alignment on plain paper
  before printing on real label stock. A **format** dropdown selects the
  label sheet — currently only Avery Zweckform L6037 (25.4 × 10 mm, 189
  labels/sheet), but the backend (`backend/labels.py`'s `LABEL_FORMATS`
  registry) and frontend (`frontend/js/labels.js`) are both structured so
  a second format is just a new registry entry + `<option>`, not a
  rewrite. New `GET /api/projects/{id}/export-labels.pdf`.

### Changed

- The default Pflichtenheft **Vorbemerkungen** text is now a much fuller
  writeup (contributed by the user): Begriffserklärungen (Sensor, Aktor,
  Szene, ETS), Grundlegende Bedienphilosophie, a per-Gewerk
  Funktionsübersicht (Beleuchtung, Beschattung, Heizung), Prioritäten/
  Schutz-/Zentralfunktionen, and a closing Hinweis footnote — replacing
  the previous shorter text (which itself replaced an even earlier one;
  both old versions are recognized and upgraded, see below). Installs
  whose preamble still exactly matches a previous default (i.e. never
  customized) get upgraded to the current one on next startup, same
  "never touch text someone actually wrote" backfill pattern used when
  this field was first introduced.
- The Vorbemerkungen field now supports light formatting - blank lines
  between paragraphs, `##`/`###` for a heading, a line that's only
  `**text**` for a smaller subheading, a line that's only `*text*` for an
  italic aside/footnote, `---` for a horizontal rule, `- ` for bullet
  points, and `**text**` inline for bold - rendered accordingly in the
  PDF (new `SubHeading`/`BodyBullet` paragraph styles in `backend/
  pdf_design.py`, plus `HRFlowable` for the rule). Previously it was
  rendered as flat paragraphs only.
- The Pflichtenheft PDF's optional **Gruppenadressen** section moved to
  always be the last section (after Klärungsliste), regardless of which
  other optional sections are also selected - it's usually the longest
  (every group address as its own table row), so it now sits after the
  more narrative sections instead of between Zentral-/Allgemeinfunktionen
  and Abgangsliste.

### Fixed

- Frontend files (`frontend/`, served as static files by `backend/
  main.py`) were browser-cacheable with no revalidation hint, so after
  the self-update flow's `git pull` + restart, a browser could keep
  serving pre-update HTML/CSS/JS until the user happened to hard-refresh
  — several reported "the update isn't showing up" cases this session
  turned out to be exactly this. Now served with `Cache-Control:
  no-cache`: the browser still keeps a local copy, but must revalidate
  it (a cheap conditional GET via the ETag Starlette's `StaticFiles`
  already sends) before using it, so a normal reload always picks up
  changed files while unchanged ones still avoid a full re-download.

## [0.2.0] - 2026-08-16

### Added

- **Duplizieren** for projects: a one-click, same-install copy (floors,
  rooms, points, specials, and metadata), available both from a project's
  own header and as a button in each row of the project list. Auto-names
  the copy "<Name> (Kopie)" (numbered if that name is already taken) and,
  from the project header, switches straight into the new copy. New
  `POST /api/projects/{id}/duplicate` endpoint - builds on the existing
  export/import-json logic (now factored into shared
  `_build_project_payload()`/`_insert_project_from_payload()` helpers) but
  skips the JSON round-trip and can never skip an item, since Point Types/
  Categories always match themselves on the same install.

- Export/import (JSON) for Setup → Kategorien, Funktionstypen, and
  Zentral-/Allgemeinfunktions-Vorlagen — the same pattern the Geräte
  Katalog already had, so the new "Alle löschen" buttons (below) are
  always recoverable without a database reset. Kategorien's import only
  renames the 6 fixed categories (matched by main group number, never
  adds/removes); Funktionstypen and Zentral-Vorlagen upsert by
  category+name(+scope), so re-importing the same file twice updates in
  place instead of duplicating. New `GET/POST .../export-json` and
  `.../import-json` endpoints for all three. The current defaults for
  all four importable sections (including the existing Geräte Katalog)
  are now committed as reference/starter files under `docs/templates/`.
- "Alle löschen" bulk-clear buttons, each with a confirmation popup, for
  the Geräte Katalog, Setup → Funktionstypen, and Setup →
  Zentral-/Allgemeinfunktions-Vorlagen — for starting over with your own
  set instead of editing/deleting the seeded defaults one by one. Geräte
  Katalog and Funktionstypen only delete entries not already used by a
  project (in-use ones are skipped and reported, never force-deleted);
  Zentral-Vorlagen have no such restriction, since nothing else
  references them by id. New `DELETE /api/actor-types`,
  `DELETE /api/point-types`, `DELETE /api/central-templates` endpoints.
- More explanation in Setup (Funktionstypen, Zentral-/Allgemeinfunktions-
  Vorlagen, Kategorien) and MANUAL.md's addressing-model section on how
  these relate to the generated GA tree, and why the
  Hauptgruppe=Kategorie/Mittelgruppe=Geschoss/Untergruppe=Punkt scheme is
  built into the tool rather than a configurable setting (KNX's own
  0–31/0–7 main/middle group limits make an alternative ordering, e.g.
  floor-as-main-group, a different addressing engine, not a toggle).
- A new **Setup → Pflichtenheft** sub-tab controls what the Pflichtenheft
  PDF export includes: the Vorbemerkungen text, plus six checkboxes —
  whether to show Vorbemerkungen at all (new, lets you keep the text
  saved but hide the section), Stockwerk-/Raumverzeichnis and
  Geräteliste (on by default, matching prior behavior), and
  **Gruppenadressen**, **Abgangsliste**, and **Klärungsliste** sections
  (off by default, since they can make a larger project's Pflichtenheft
  very long) — `company_profile` gained six new columns for these
  toggles. The Abgangsliste export's per-floor/actuator/channel
  rendering was factored out into a shared `build_abgangsliste_story()`
  so both the standalone export and this optional section use the same
  code.
- The default Vorbemerkungen text (seeded on fresh installs) now covers
  more ground - Beleuchtung, Rollladen/Jalousie treated separately,
  Heizung, and Zentral-/Wetterfunktionen - condensed from common
  real-world Pflichtenheft templates without their page-length detail.
  Installs that already had a `company_profile` row before this default
  text existed (so the fresh-install seed never touched them) get it
  backfilled on next startup too, but only if the field is still empty -
  never overwrites text someone has actually written.
- Pflichtenheft PDF, made more professional: a **Vorbemerkungen** section
  (general operating-convention text, editable/clearable in the new Setup
  → Pflichtenheft tab, seeded with sensible default wording on fresh
  installs), a **Stockwerk- und Raumverzeichnis** table, and a
  **Getestet** checkbox next to every individual function (room-level and
  central/general) for hand-ticking during on-site commissioning —
  paper-style only, no tracked state, since KNXpilot doesn't know which
  physical button/Bedienelement drives which function (that's ETS
  programming).
- A new **Übergabe-Checkliste** PDF export (Pflichtenheft sub-tab, next
  to the existing PDF button): a mostly generic KNX handover checklist
  (Sichtprüfung/Funktionsprüfung/Kundengespräch/Anlagenübergabe, tri-state
  Ja/Nein/Nicht-nötig checkboxes, Bemerkungen column, signature lines for
  Errichter and Kunde/Betreiber) - only the project name is filled in
  automatically.
- A "Projekt öffnen" picker modal (nav dropdown → **Projekt öffnen**):
  search across all projects and open one directly, from any tab,
  without needing to close whatever project is currently open first —
  picking a project always switches straight to it.
- A small 📁 project-name badge in the header, visible from every tab
  once a project is open, with its own **×** to close directly (no need
  to go back to the Projekte tab first). Updates live on open, rename,
  and delete.
- A new **Hilfe** tab renders the full usage manual (`MANUAL.md`) in-app,
  via a new `GET /api/system/manual` endpoint and `frontend/js/hilfe.js`.
  The Markdown-to-HTML renderer that used to be private to the Update
  tab's changelog view moved into `frontend/js/ui.js` as a shared,
  general-purpose `renderMarkdown()` (now also supports arbitrary
  heading depth and fenced code blocks, needed for the manual's KNX
  addressing table and CSV format block).
- README.md screenshots (`docs/screenshots/`): Übersicht, Funktionen,
  Gruppenadressen, and Abgangsliste.
- A GitHub Actions workflow (`.github/workflows/docker-publish.yml`)
  builds and publishes the Docker image to `ghcr.io/seaspotter/knxpilot`
  on every push to `main` (tag `latest`, plus a short-sha tag) and on
  version tags (e.g. `v0.1.0`), as a multi-arch manifest covering
  `linux/amd64` and `linux/arm64` (e.g. Raspberry Pi) — `docker compose
  pull` picks the right one for the host automatically.
- A small version badge in the header (e.g. `v0.1.0`, or
  `v0.1.0-3-gabc1234` for commits since the last release), from a new
  `GET /api/system/version` endpoint (`git describe`, local checkout
  only — no network fetch, unlike the existing update-check endpoint).

### Changed

- The Firma and Pflichtenheft tabs' save buttons now both read simply
  "Speichern" instead of "Firmenprofil speichern" — clearer given both
  tabs save fields on the same underlying profile record.
- The app's accent color (buttons, headings, active-tab underline,
  links) changed from blue to green, and the PDF exports' banner/table-
  header/section-heading color changed from dark navy to dark green —
  no more blue left anywhere in the design system.
- Export/Import/"Alle löschen" for the Geräte Katalog and Setup →
  Kategorien/Funktionstypen/Zentral-Vorlagen moved from a row of wide
  text buttons into a compact icon-button group in each card's top-right
  corner (hover for a tooltip). Import now opens a small popup to choose
  the file instead of an always-visible file picker next to the button —
  new shared `openImportModal()` helper in `frontend/js/ui.js`.
- The projects list's "Aus Sicherung wiederherstellen" and the opened
  project's "Sichern (JSON)" moved the same way, into icon buttons (⭱ in
  the list header, ⭳ next to the new ⧉ Duplizieren icon in the project
  header) instead of a wide text button/inline file input.
- README.md is now a short landing page (pitch, screenshots, key
  features, quickstart, links) instead of the full manual — all detailed
  per-tab usage instructions, the GA addressing model, and the CSV
  format moved to the new `MANUAL.md` (also viewable in-app via Hilfe).
- `docker-compose.yml` now pulls the published `ghcr.io/seaspotter/
  knxpilot:latest` image instead of building locally — a fresh deploy or
  a dependency update is now `docker compose pull && docker compose up
  -d`, no local build tools needed on the server. Building locally is
  still possible by swapping the `image:` line for `build: .`.
- The self-update mechanism's "requirements.txt/Dockerfile changed"
  message (`backend/routers/system.py`) now points at `docker compose
  pull && docker compose up -d` instead of `docker compose up -d
  --build`, matching the new image-based deploy flow.

## [0.1.0] - 2026-08-16

First release: the backend/frontend restructuring plus the full UI/UX
rework that followed it (toasts/modals, workflow dashboard, interactive
GA tree, mobile pass, bulk room add, focused views, nav dropdown,
in-app changelog, editable structure/functions/setup, and the
Gruppenadressen split) — see below for the full detail.

### Added

- Toast notifications and a custom confirm modal (`frontend/js/ui.js`),
  replacing every native `alert()`/`confirm()` call across the frontend
  (24 + 7 call sites).
- An open-circuit-count badge on the Abgangsliste sub-tab button (e.g.
  "Abgangsliste (3)"), mirroring the existing Klärungsliste badge pattern.
- A new "Übersicht" sub-tab (`frontend/js/uebersicht.js`), now the default
  landing sub-tab when opening a project — 5 clickable status cards (one
  per other sub-tab) summarizing floors/rooms/points, circuit assignment
  progress, planned device count, and open Klärungen at a glance, each
  jumping straight to the relevant sub-tab on click.
- The Gruppenadressen preview is now a collapsible tree (native
  `<details>`/`<summary>`, `.ga-tree` in `frontend/css/style.css`) instead
  of one long block of monospace text — main groups open by default,
  middle groups (the actual source of clutter on larger projects) start
  collapsed, each showing an address count. "Alle aufklappen"/"Alle
  einklappen" buttons toggle everything at once.
- A responsive pass for phones/small tablets (`@media (max-width: 700px)`
  in `frontend/css/style.css`): the main nav and project sub-nav scroll
  horizontally instead of overflowing the page (the sub-nav has 6 buttons
  now after the Übersicht addition), list rows reflow instead of clipping,
  and touch targets are slightly larger. Purely additive — desktop layout
  is unaffected.
- Bulk room add: each floor's room quick-add now has a "Mehrere..."
  toggle revealing a textarea to paste multiple room names at once (one
  per line), instead of adding them one-by-one. Frontend-only, reuses the
  existing single-room endpoint in a loop; the original single-room input
  is unchanged.
- Floors, rooms, and room functions can now be renamed/edited after
  creation, not just deleted: floor and room names via a "Bearbeiten"
  button opening a rename dialog (`frontend/js/ui.js`'s
  `openRenameModal`), and a room's assigned functions (point type/label/
  BWM) via a ✎ edit link on each pill that repurposes the existing
  quick-add form into an edit form (same pattern already used for actor
  types). New backend endpoints: `PUT /api/floors/{id}`,
  `PUT /api/rooms/{id}`, `PUT /api/room-points/{id}`.
- Setup's Funktionstypen (formerly "Punkttypen") and Zentral-Vorlagen can
  now be edited in place (the backend already supported this; only the
  frontend UI was missing) — same "Bearbeiten" pattern as the Geräte
  Katalog's actor types.
- Categories can now be renamed via a new "Bearbeiten" button
  (`PUT /api/categories/{id}`) — reordering/adding/removing stays
  unsupported, since order directly maps to fixed KNX main group numbers.

### Changed

- Split the GA tree preview and CSV export out of the "Funktionen"
  sub-tab into its own new "Gruppenadressen" sub-tab, so that assigning
  functions to rooms and viewing/exporting the resulting group addresses
  are no longer stacked on the same page. Frontend-only — the moved code
  (`previewGA`, `expandAllGaTree`, `downloadCSV`) now lives in a new
  `frontend/js/gruppenadressen.js`, following the one-file-per-sub-tab
  convention. The tree now loads automatically when opening the tab
  (the "Vorschau" button still works, as a manual refresh), and
  Übersicht gained a matching "Gruppenadressen" stat card showing the
  total address count.
- Renamed Setup's "Punkttypen" sub-tab and every user-facing label to
  "Funktionstypen", for terminology consistency with the "Funktionen"
  tab where those types get assigned to rooms (the underlying
  `point_types` table, `/api/point-types` endpoint, and JS variable
  names are unchanged — only displayed text moved).
- Floor and room rename now uses a "Bearbeiten" button in the same
  button row as "löschen", instead of the ✎ icon-link introduced in the
  previous change — matching the convention used everywhere else a name
  can be changed (actor types, Funktionstypen, Zentral-Vorlagen,
  Kategorien). Room-function pills keep their ✎/× icon-link pair, which
  predates this rework and fits a compact pill format better than a
  text button.
- Split the "Gruppenadressen" sub-tab into **Gebäudestruktur** (floors/
  rooms only) and **Funktionen** (assigning KNX functions to rooms,
  Sonderadressen, GA preview/export) — these were previously combined on
  one page. `frontend/js/funktionen.js` is a new file for the latter,
  following this project's one-file-per-sub-tab convention.
- Renamed the "Setup (Kategorien & Vorlagen)" tab to plain "Setup".
- Reworked the Projekte and Setup tabs from "everything stacked on one
  page" into focused views: the Setup tab now has a Firma/Kategorien/
  Punkttypen/Zentral-Vorlagen sub-nav (same pattern as the project
  workspace) instead of 4 always-visible cards; opening a project now
  hides the project list instead of leaving it visible above the
  workspace; and "create project" is now a modal (auto-focused, opens
  the new project directly on success) instead of an always-visible
  inline form. `frontend/js/ui.js`'s `showConfirm` now shares its
  overlay/Escape/backdrop-click plumbing with the new modal via a
  `openModal()` helper.
- The "Projekte" top-nav item is now a small dropdown (▾) with "Neues
  Projekt" and "Projekt öffnen", usable from any tab.
- Renamed the "Geräte" tab to "Geräte Katalog" for clarity (and the
  validation messages that reference it).
- The Update tab now shows this project's changelog
  (`GET /api/system/changelog`, new `.changelog` rendering in
  `frontend/js/update.js` — a small hand-written Markdown-to-HTML
  converter, no library added).
- Restructured the project into separate `backend/` (FastAPI) and
  `frontend/` (plain HTML/CSS/JS, no build step) directories, replacing the
  previous single `app/` directory whose `static/index.html` held the
  entire frontend inline.
- Split the 1800-line monolithic `frontend/index.html` into a CSS file
  (`frontend/css/style.css`) and one JS file per UI tab/sub-tab under
  `frontend/js/`, mirroring the existing one-router-per-tab structure of
  the backend. No behavior changes.
- Added `CLAUDE.md`, `DEVELOPMENT.md`, and `DEPLOYMENT.md`; trimmed the
  corresponding "Persistenz & Deployment" and "Code-Struktur" sections out
  of `README.md` in favor of pointers to the new files.
- Updated `Dockerfile`, `.gitignore`, and `docker-compose.yml` comments for
  the new `backend/`/`frontend/` paths (the repo-wide bind mount itself is
  unaffected).
- Added a "Keep docs in sync with code changes" section to `CLAUDE.md`.

### Fixed

- The GA tree preview's expand/collapse triangles sat flush against the
  card's left edge instead of aligning with the rest of the card's
  content (`.ga-tree summary`'s `list-style-position: outside` pushed
  the native disclosure marker outside the content box). Changed to
  `inside`.
- List rows (`ul.list li`, used by Funktionstypen, Zentral-/
  Allgemeinfunktions-Vorlagen, Kategorien, actor types, etc.) let their
  "Bearbeiten"/"Löschen" buttons wrap onto a second line whenever the
  row's content wrapped to multiple lines (e.g. "LED (Tunable White)",
  "Klima"), since content and buttons shared equal flex-shrink. Fixed by
  giving the content column `min-width: 0` (free to shrink/wrap) and the
  button column `flex-shrink: 0` (stays put at its natural size).
- `DEPLOYMENT.md`'s Proxmox instructions named `docker-compose-plugin`/
  `docker-ce` as an apt-installable fallback without noting that those are
  Docker's own package names, not Ubuntu's — `apt install` silently fails
  the whole transaction (including `docker.io`) when one package name
  doesn't resolve. Fixed to use Ubuntu's own `docker-compose-v2` package
  (no third-party repo needed), with Docker's official install script kept
  as a documented fallback for distros where that package isn't available.
