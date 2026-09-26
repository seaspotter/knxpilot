# FINDINGS: ETS project files (.knxproj)

Groundwork for the roadmap item ".knxproj / ETS import" (see
[`ROADMAP.md`](../ROADMAP.md)). Rule for this feature: **check every
assumption against real ETS exports before writing import code**, and write
down here where reality differs. Where this file and the code disagree,
this file is updated first.

**Status (2026-09-26): nothing verified yet.** Everything under
"Hypotheses" comes from publicly known descriptions of the format, not from
a real export. Next step: run the probe on 2–3 real exports (ideally one
ETS5, one ETS6, one password-protected) and fill in the "Verified" column.

```bash
python tools/knxproj_probe.py path/to/project.knxproj
```

`tools/knxproj_probe.py` is read-only and standard-library-only; it prints
the archive layout, encryption, XML namespace, group ranges/addresses and
the building structure. Paste relevant parts of its output below.

## Hypotheses

| # | Hypothesis | Verified | Notes |
|---|---|---|---|
| H1 | A `.knxproj` is a ZIP archive containing `knx_master.xml` (master data: DPTs, manufacturers), one project part per project, and `M-XXXX/` folders with manufacturer product data. | – | |
| H2 | The project part is either a folder `P-XXXX/` or a nested archive `P-XXXX.zip`; the nested archive is AES-encrypted when the project has a password. | – | The probe reports "PASSWORD-PROTECTED" for this case. |
| H3 | Group addresses live in `P-XXXX/0.xml` under `Installations/Installation/GroupAddresses/GroupRanges`, as nested `GroupRange` (main, middle) with `GroupAddress` children. | – | |
| H4 | `GroupAddress/@Address` is an integer; 3-level decoding is main = n >> 11, middle = (n >> 8) & 7, sub = n & 255. `RangeStart`/`RangeEnd` use the same encoding. | – | The probe prints both the raw value and the decoded address; compare with ETS. |
| H5 | `GroupAddress/@DatapointType` holds values like `DPST-1-1` (same notation as KNXpilot's CSV), may contain several space-separated values, and may be missing. | – | |
| H6 | The building structure is under `Locations` as nested `Space` elements with `Type` = Building / BuildingPart / Floor / Room / Corridor / Stairway / DistributionBoard (ETS6); ETS5 uses `Buildings/BuildingPart` instead. Rooms reference devices via `DeviceInstanceRef`. | – | |
| H7 | Devices are under `Topology/Area/Line/DeviceInstance` with `@Address` (physical address within the line) and `@ProductRefId`, resolvable to manufacturer/order number via the `M-XXXX/` product data. | – | Needed to match devices against the Geräte Katalog. |
| H8 | The root element's namespace encodes the schema version (e.g. `http://knx.org/xml/project/20` … `/23`), which differs between ETS5 and ETS6 releases. | – | Decides how many format variants the import must handle. |

## What an import could map to KNXpilot

| ETS | KNXpilot | Confidence |
|---|---|---|
| Floors/rooms from `Locations` | Gebäudestruktur (floors, rooms) | high, if H6 holds |
| Devices in rooms + product refs | Geräteplanung, matched to the Geräte Katalog by manufacturer + model/order number | medium - catalog models must match ETS naming |
| Group addresses (name, address, DPT) | a baseline for "Änderungen seit dem letzten ETS-Export" | high - lets the diff start from the real ETS state instead of the last CSV |
| Group addresses → functions | Funktionen (room points) | **low** - KNXpilot *generates* addresses from functions; going backwards only works for projects that follow KNXpilot's naming scheme ("{Raum} {Label} {Suffix}"). Anything else would be guesswork - better to import structure and devices and plan functions in KNXpilot. |

## Open questions

- **Password-protected projects:** reading the encrypted nested archive
  needs an AES-capable ZIP library (the standard library's `zipfile` can't),
  i.e. a new dependency such as `pyzipper`, plus the documented derivation
  of the archive password from the project password. Decide: support it, or
  ask users to export without a password.
- **Existing library:** `xknxproject` (Python) already parses `.knxproj`
  files including encrypted ones. Before using it, check that its license is
  compatible with KNXpilot's AGPL-3.0 and whether its output covers what we
  need - otherwise a small own parser (standard library only) is enough for
  H3–H7.
- **Scope of the first version:** structure + devices only (recommended,
  see mapping table), or also group addresses as the ETS-diff baseline?
