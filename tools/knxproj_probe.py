"""
Read-only probe for ETS project exports (.knxproj) - run it on a real
export to check the assumptions in docs/FINDINGS-knxproj.md before the
ETS import gets built. Standard library only; never writes anything.

    python tools/knxproj_probe.py path/to/project.knxproj

Prints the archive layout, whether the project part is password-protected,
the XML namespace/schema version, the group address ranges and a sample of
group addresses (decoded to main/middle/sub), and the building structure
(Locations/Buildings). Paste the output into docs/FINDINGS-knxproj.md.
"""
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter


def local(tag):
    return tag.rsplit("}", 1)[-1]


def decode_3level(value):
    n = int(value)
    return f"{n >> 11}/{(n >> 8) & 0x7}/{n & 0xFF}"


def walk(el, depth, lines, limit):
    """Building structure: Space (ETS6) / BuildingPart (ETS5) elements."""
    if len(lines) >= limit:
        return
    if local(el.tag) in ("Space", "BuildingPart"):
        devices = sum(1 for c in el if local(c.tag) == "DeviceInstanceRef")
        lines.append(f"{'  ' * depth}- {el.get('Type')}: {el.get('Name')!r}" + (f" ({devices} Geräte)" if devices else ""))
        depth += 1
    for child in el:
        walk(child, depth, lines, limit)


def probe_project_xml(data, label):
    root = ET.fromstring(data)
    print(f"\n== {label}")
    print(f"root: <{local(root.tag)}> namespace: {root.tag[1:].split('}')[0] if root.tag.startswith('{') else '-'}")
    for key in ("CreatedBy", "ToolVersion"):
        if root.get(key):
            print(f"{key}: {root.get(key)}")
    counts = Counter(local(e.tag) for e in root.iter())
    print("element counts:", {k: counts[k] for k in ("GroupRange", "GroupAddress", "DeviceInstance", "Space", "BuildingPart", "ComObjectInstanceRef") if counts[k]})

    ranges = [e for e in root.iter() if local(e.tag) == "GroupRange"]
    print(f"\nGroupRange ({len(ranges)}):")
    for r in ranges[:25]:
        start, end = r.get("RangeStart"), r.get("RangeEnd")
        span = f"{decode_3level(start)} .. {decode_3level(end)}" if start and end else "?"
        print(f"  {r.get('Name')!r}: RangeStart={start} RangeEnd={end} -> {span}")

    gas = [e for e in root.iter() if local(e.tag) == "GroupAddress"]
    print(f"\nGroupAddress sample ({len(gas)} total):")
    for g in gas[:30]:
        addr = g.get("Address")
        print(f"  Address={addr} -> {decode_3level(addr) if addr and addr.isdigit() else '?'} "
              f"Name={g.get('Name')!r} DPT={g.get('DatapointType')!r} attrs={sorted(g.attrib)}")
    print("DatapointType values:", Counter(g.get("DatapointType") for g in gas).most_common(15))

    lines = []
    walk(root, 0, lines, 60)
    print(f"\nBuilding structure ({'first 60 lines' if len(lines) >= 60 else len(lines)}):")
    print("\n".join(lines) or "  (none found)")


def main(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        print(f"== archive: {path}\n{len(names)} entries")
        for n in names[:40]:
            print(f"  {n}")
        if len(names) > 40:
            print(f"  ... {len(names) - 40} more")
        for n in names:
            if n.lower().endswith(".zip") and n.upper().startswith("P-"):
                with z.open(n) as inner_file, zipfile.ZipFile(inner_file) as inner:
                    encrypted = any(i.flag_bits & 0x1 for i in inner.infolist())
                    print(f"\nnested project archive {n}: {'PASSWORD-PROTECTED (encrypted)' if encrypted else 'not encrypted'}")
                    print("  entries:", inner.namelist()[:20])
                    if not encrypted:
                        for m in inner.namelist():
                            if m.endswith("0.xml"):
                                probe_project_xml(inner.read(m), f"{n}/{m}")
        for n in names:
            if n.upper().startswith("P-") and n.endswith("/0.xml"):
                probe_project_xml(z.read(n), n)
            elif n.upper().startswith("P-") and n.endswith("project.xml"):
                root = ET.fromstring(z.read(n))
                info = next((e for e in root.iter() if local(e.tag) == "ProjectInformation"), None)
                if info is not None:
                    print(f"\n== {n}: ProjectInformation attrs: {dict(info.attrib)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
