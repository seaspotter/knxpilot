# KNX Group Address Generator (v2)

Built directly from analysis of real ETS6 exports. Workflow:

**Floors → Rooms → Points (lights / sockets / windows / heating) → done.**
Central and general functions (date/time, weather station, "all lights off"
per floor, etc.) are generated automatically from templates — you normally
never touch those per project.

## Addressing model (matches your real projects)

| KNX level    | Mapped to |
|--------------|-----------|
| Main Group   | Function category: `Allgemein, Beleuchtung, Steckdosen, Heizung, Rollo, Tore` |
| Middle Group | `Zentralfunktionen` (central/collective) + one per Floor |
| Sub Group    | One address block per physical point: `{Room} {Label} {Suffix}` |

Each point reserves a **fixed address block** (default 5, or 10 for blinds
with slats/Lamelle) and pads unused slots with `res` for future expansion —
exactly like your existing projects.

## CSV format — verified against your real exports

Tab-separated, every field quoted, header row included, columns:
```
Main  Middle  Sub  Address  Central  Unfiltered  Description  DatapointType  Security
```
DPTs are written as `DPST-x-y`. `Security` is always `Auto`. This was
checked byte-for-byte against `Landes.csv`, `Steiner.csv`, and
`Mayrhofer.csv` — all three used an identical format, so this should import
directly via ETS6 → right-click **Group Addresses** → **Import Group
Addresses**.

If you ever change conventions in ETS and imports start getting skipped,
re-export a small test project and diff it against the tool's output —
the CSV writer is isolated in `export_csv()` in `app/main.py`.

## How to use it

The tool has four tabs:

- **Gruppenadressen** — build projects (Floors → Rooms → Points), preview,
  and export the ETS6 Group Address CSV. This was previously called
  "Projects".
- **Abgangsliste** — pick a project, add the actuators you're installing,
  and wire each circuit to a channel.
- **Aktoren** — your global actuator hardware catalog (Hersteller / Modell /
  Type / Channels), shared across every project.
- **Setup** — Categories, Point Types, and Central/General Templates.
  Rarely touched day-to-day; seeded with your conventions already.

### Setup tab

- **Categories** — the 6 Main Groups, pre-seeded.
- **Point Types** — reusable definitions like "Licht (Dimmen)", "Rollo
  (einfach)", "Jalousie (mit Lamelle)", "Heizkreis", each with its
  datapoints, reserved block size, and a **channel type** (e.g. `Schalten`,
  `Dimmen`, `Rollo`, `Heizung`, `Tor`) that links it to matching Actor
  Types for the Abgangsliste.
- **Central/General Templates** — auto-generated blocks:
  - `scope: building` → one block for the whole project
  - `scope: floor` → one block per floor (e.g. "Zentral EG", "Zentral OG")
  - `scope: room_multi` → one block **per room**, only for rooms with at
    least a set number of points in that category (default 2). E.g.
    Rollo has this pre-configured: any room with 2+ blinds automatically
    gets its own "{Room} Zentral Auf/Ab/Stop/Position" (padded to a block
    size, e.g. 5) plus a single "{Room} Sperre" address for a
    Langschläfer/sleep-in override — driven purely by how many blinds
    you add to that room, no manual setup needed.
  - "Skip outdoor/unheated floors" (floor scope only) → excludes floors
    marked as outdoor (e.g. "Fahrzeitmessung" or "Sommer/Winter Status"
    per floor makes no sense for "Aussen")
  - Allgemein category templates (Datum/Uhrzeit, Klima) each become their
    own Middle Group, generated once per project regardless of floor count.
- **A category's whole Main Group is only generated if it's actually
  used** in the project — e.g. if you never add a Steckdose, no
  Steckdosen Main Group or its central function appears at all.

### Gruppenadressen tab

- Create a project, add your Floors (Stockwerke). Mark a floor as
  **Outdoor/unheated** (e.g. "Aussen", "Garage") if it should be excluded
  from templates flagged that way.
- Add Rooms per floor.
- For each room, add Points: pick a Point Type (e.g. "Licht (Dimmen)"),
  give it a label (e.g. "Spots", "Decke", "Nord" for a window), a
  quantity if you want several identical ones at once, and tick **+BWM**
  if that point needs a motion sensor address.
- **Anything special** (a one-off scene, a custom central group for a
  specific room like "Kind1 Zentral") goes in **Special / Extra
  Addresses** — pick the category, choose whether it belongs in
  `Zentralfunktionen` or a specific floor, name it, and give it its
  datapoints.
- **Preview** to sanity check the tree, then **Download CSV** for ETS6.
- **⭳ Backup (JSON)** saves the full project definition (floors, rooms,
  points, specials) as a `.json` file — separate from the ETS CSV, this
  is for backing up / duplicating / moving a project between installs.
  **⭱ Restore from Backup** on the Projects list re-creates a project
  from that file. It matches Point Types/Categories by name against
  what exists on the destination install; anything that doesn't match
  is skipped and reported, never silently guessed at. If a project with
  the same name already exists, the import is saved as "<name>
  (imported)" rather than overwriting it.
- **× Close** collapses the open project's detail view without deleting
  anything — useful once you have several projects and the page gets long.

### Aktoren tab

Your actuator hardware catalog — **global, shared across every project**
(same list whichever project you're wiring). Each entry has:

- **Hersteller** (manufacturer, e.g. "MDT")
- **Modell** (model, e.g. "AKS-2016.03")
- **Type** — must match a Point Type's channel type (`Schalten`, `Dimmen`,
  `Rollo`, `Heizung`, `Tor`, or a custom one you've added) to be assignable
  to it
- **Channels** — how many physical outputs it has

**⭳ Export catalog (JSON)** / **⭱ Import catalog (JSON)** let you back up
or share this catalog. Import matches by (Hersteller, Modell): if that
combination already exists it updates the Type/Channel count in place,
otherwise it adds a new entry — safe to re-import the same file repeatedly.

### Where projects are actually stored

Projects live in the SQLite file `app/data/knx_ga.db`, which is bind-mounted
via `docker-compose.yml` to `./data` on the host — so it survives container
rebuilds/restarts as long as that folder isn't deleted. The JSON backup/
restore feature above is for explicit portability (moving a project to
another machine, or keeping an external copy), not required for normal
day-to-day persistence.

### Abgangsliste (Actuator wiring / circuit list)

Once your project has rooms and points defined, the tool already knows every
physical output you need (every switch, dimmer, blind, and heating channel).
The **Abgangsliste** tab turns that into a wiring list for the electrician:

1. **Setup → Point Types**: each point type has a **channel type** (e.g.
   `Schalten`, `Dimmen`, `Rollo`, `Heizung`, `Tor`) and **channels needed**
   (usually 1). This is pre-filled for all the built-in point types.
2. **Aktoren tab**: define your actuator hardware catalog — e.g.
   Hersteller "MDT", Modell "AKS-2016.03", Type `Schalten`, 20 channels.
   The Type must match a Point Type's channel type to be assignable to it.
   This catalog is global and shared across every project.
3. **Abgangsliste tab**: pick a project from the dropdown, then add the
   actual **Actuators** you're installing (pick the Actor Type, which
   floor/UV it lives in, its location label, and physical KNX address like
   `1.1.2`).
4. Every **Circuit** (one row per physical output your rooms need) shows up
   below with a dropdown of all channels from matching actuators. Pick one
   manually, or click **Auto-assign all** to fill every unassigned circuit
   into the first free matching channel automatically (in floor/room order).
5. **Download Abgangsliste (CSV)** exports a sheet with columns `Geschoss,
   Raum/UV, Aktor, Physikalische Adr., Kanal, Funktion` — every channel of
   every actuator is listed, with unused ones marked `RESERVE`, matching the
   layout of a hand-built electrician's wiring sheet.

This is a separate export from the ETS Group Address CSV — one is for
programming the bus, the other is for wiring the panel.

### A note on customer documentation exports

You mentioned possibly wanting a customer-facing documentation export later
(nicer formatting, descriptions, etc.) — the current CSV export is
ETS-import-focused, not meant for that. When you're ready, this is a
natural next addition (e.g. a formatted Word/PDF or Markdown table per room
built on the same `build_ga_tree()` data used for the CSV) — happy to build
that whenever you want it.

## Running with Docker

```bash
docker compose up -d --build
```
Open `http://<host>:8000`. Data persists in `./data/knx_ga.db` (bind mount).

## Upgrading from an earlier version of this tool

The database schema auto-migrates (adds new columns) on startup, so an
existing `knx_ga.db` keeps working. However, the *seed data* (Point Types,
Central Templates) is only inserted once, when the categories table is
empty — so naming fixes like "Schalten Status" or the restructured
Sommer/Winter templates won't retroactively appear in an existing install.
Since this tool has likely not accumulated real project data yet, the
simplest path is to delete `./data/knx_ga.db` and let it reseed fresh:

```bash
docker compose down
rm ./data/knx_ga.db
docker compose up -d --build
```

If you do have real projects saved, back them up first with the new
**⭳ Backup (JSON)** button on each project before wiping the database, then
restore them afterward via **⭱ Restore from Backup**.

## Deploying on Proxmox

Same as before — a lightweight LXC with Docker is the simplest option:

1. Create an unprivileged Debian/Ubuntu LXC (1 vCPU / 512MB–1GB RAM is plenty).
2. Enable **nesting** (Options → Features) so Docker can run inside the LXC.
3. `apt update && apt install -y docker.io docker-compose-plugin`
4. Copy this folder in, `cd` into it, `docker compose up -d --build`.
5. Browse to `http://<lxc-ip>:8000`.

The LXC's filesystem (including `./data`) is covered by your normal Proxmox
backup jobs automatically.

## Notes / limitations

- Single-user, no auth — keep it on your internal network.
- No `.knxproj` manipulation — only the officially-supported CSV import path.
- ETS's import always overwrites matching entries and never deletes ones
  missing from the file — regenerating/reimporting won't clean up addresses
  you've since removed from the tool; do that manually in ETS if needed.
- Reserved `res` blocks are a deliberate choice from your existing
  convention (future-proofing) — if a point type (plus BWM, if ticked) ever
  needs more suffixes than its block size, the tool just continues past the
  block boundary without padding, so following points shift down. Keep
  block sizes generous enough for the point types you actually use.
- A category's Main Group only appears if something in the project actually
  uses it (a point, or a special item). Central templates for an unused
  category are not generated either.
- "Skip outdoor/unheated floors" on a central template is per-template, not
  a blanket floor exclusion — e.g. Beleuchtung's "Zentral {Floor}" still
  includes an outdoor floor unless you tick that box for it too.

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) — see
[`LICENSE`](./LICENSE). Chosen specifically because this is a network
service (a web app): AGPL closes the "SaaS loophole" that plain GPL has —
if someone runs a modified version of this tool as a hosted service, they
must make that modified source available to its users too, not just to
people they hand a compiled copy to.

Before publishing, replace "the project author(s)" in the license header
at the top of `app/main.py` with your actual name or company.
