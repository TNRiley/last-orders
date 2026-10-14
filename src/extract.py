#!/usr/bin/env python
"""Pull named pubs and railway/canal geometry out of the Great Britain OSM extract.

Reads  src/raw/great-britain-latest.osm.pbf   (Geofabrik, ~2.1 GB)
Writes src/raw/pubs.json   every named amenity=pub, plus the disused:amenity=pub spellings
       src/raw/lines.json  railway and canal geometry, classed open / closed

Two sequential reads of the file, and the file is the whole cost: on this machine it
streams at only a few MB a second (real-time virus scanning), so a pass takes minutes
while using almost no CPU. Everything is therefore arranged to need as few passes as
possible, and to filter inside libosmium rather than in Python:

  pass 1  one TagFilter of ~140 explicit key=value pairs, over nodes and ways at once
          -> pub nodes (which carry their own coordinates) and the ways worth keeping
  pass 2  an IdFilter of exactly the node ids pass 1 asked for
          -> the coordinates those ways need

Two traps were hit getting here, both worth keeping written down:

  * `with_locations()` looks like the obvious way to get way geometry. It writes an index
    entry for every node in the extract - about 130 million of them - and on this machine
    managed roughly 2 % of the file in five minutes. Don't.
  * a KeyFilter on "waterway" surfaces every stream, ditch and drain in Britain to
    Python. Filter on key=value pairs, which keeps the rejection in C++.
"""
import json
import sys
import time
from array import array
from pathlib import Path

import numpy as np
import osmium
import osmium.filter as F

HERE = Path(__file__).resolve().parent
PBF = HERE / "raw" / "great-britain-latest.osm.pbf"
RAW = HERE / "raw"

# railway=* values meaning "trains can run here today". service=siding/yard/spur are
# kept - still live metal - and recorded so analyse.py can drop them to test sensitivity.
OPEN_RAIL = {"rail", "light_rail", "narrow_gauge", "subway", "tram",
             "monorail", "funicular", "preserved", "miniature"}
# railway=* values meaning "there was a line here once"
CLOSED_RAIL = {"abandoned", "dismantled", "razed", "disused", "demolished", "removed"}

LIFECYCLE_RAIL = ("disused:railway", "abandoned:railway", "razed:railway",
                  "dismantled:railway", "demolished:railway", "removed:railway",
                  "historic:railway")
LIFECYCLE_WATER = ("disused:waterway", "abandoned:waterway", "razed:waterway",
                   "dismantled:waterway", "former:waterway")
PUB_KEYS = ("amenity", "disused:amenity", "abandoned:amenity", "was:amenity",
            "former:amenity", "demolished:amenity", "razed:amenity")


def tag_pairs():
    """Every key=value pair worth surfacing, as one OR-ed filter.

    TagFilter needs explicit values, so the lifecycle keys are expanded over every
    railway value they are plausibly spelled with, plus a bare "yes".
    """
    pairs = [("railway", v) for v in sorted(OPEN_RAIL | CLOSED_RAIL)]
    pairs += [("waterway", "canal")]
    for k in LIFECYCLE_RAIL:
        pairs += [(k, v) for v in sorted(OPEN_RAIL | CLOSED_RAIL | {"yes"})]
    pairs += [(k, "canal") for k in LIFECYCLE_WATER]
    pairs += [(k, "pub") for k in PUB_KEYS]
    return pairs


def line_class(tags):
    """Return (kind, state) for a way worth keeping, else None."""
    rw = tags.get("railway")
    if rw in OPEN_RAIL:
        return ("rail", "open")
    if rw in CLOSED_RAIL:
        return ("rail", "closed")
    for k in LIFECYCLE_RAIL:
        if k in tags and tags[k] != "no":
            return ("rail", "closed")

    ww = tags.get("waterway")
    if ww == "canal":
        if tags.get("disused") == "yes" or tags.get("abandoned") == "yes":
            return ("canal", "closed")
        return ("canal", "open")
    for k in LIFECYCLE_WATER:
        if tags.get(k) == "canal":
            return ("canal", "closed")
    return None


def pub_state(tags):
    """"open", "former", or None - from whichever amenity key the pub is filed under."""
    if tags.get("amenity") == "pub":
        return "open"
    for k in PUB_KEYS[1:]:
        if tags.get(k) == "pub":
            return "former"
    return None


def pub_record(tags, osm_id, kind, lat, lon):
    return {
        "id": f"{kind}{osm_id}",
        "name": tags.get("name"),
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "state": pub_state(tags),
        "operator": tags.get("operator"),
        "brewery": tags.get("brewery"),
        "start_date": tags.get("start_date"),
        "building": tags.get("building"),
        "listed": tags.get("heritage") or tags.get("listed_status"),
    }


def main():
    if not PBF.exists():
        sys.exit(f"missing {PBF} - download the Geofabrik extract first (see README)")
    t0 = time.time()

    def elapsed():
        return f"{time.time() - t0:6.1f}s"

    # ------------------------------------------- pass 1: pub nodes and candidate ways
    print(f"[{elapsed()}] pass 1: nodes and ways, {len(tag_pairs())} tag pairs ...", flush=True)
    pubs = []
    line_ways = []   # (osm_id, kind, state, tag, service, name, node refs)
    pub_ways = []    # (tags, osm_id, node refs)
    seen = 0
    for obj in (osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY)
                .with_filter(F.TagFilter(*tag_pairs()))):
        seen += 1
        tags = dict(obj.tags)
        if obj.is_node():
            if pub_state(tags) and tags.get("name"):
                pubs.append(pub_record(tags, obj.id, "n", obj.location.lat, obj.location.lon))
            continue
        cls = line_class(tags)
        if cls:
            refs = array("q", (n.ref for n in obj.nodes))
            if len(refs) >= 2:
                line_ways.append((obj.id, cls[0], cls[1],
                                  tags.get("railway") or tags.get("waterway") or "",
                                  tags.get("service"), tags.get("name"), refs))
        if pub_state(tags) and tags.get("name"):
            pub_ways.append((tags, obj.id, array("q", (n.ref for n in obj.nodes))))
    print(f"[{elapsed()}] {seen:,} objects surfaced: {len(pubs):,} pub nodes, "
          f"{len(line_ways):,} line ways, {len(pub_ways):,} pub footprints", flush=True)

    # ----------------------------------------------- pass 2: the coordinates they need
    need = np.unique(np.concatenate(
        [np.frombuffer(w[6], dtype=np.int64) for w in line_ways]
        + [np.frombuffer(w[2], dtype=np.int64) for w in pub_ways]))
    print(f"[{elapsed()}] pass 2: resolving {len(need):,} node ids ...", flush=True)
    got_id = np.empty(len(need), dtype=np.int64)
    got_lat = np.empty(len(need), dtype=np.float64)
    got_lon = np.empty(len(need), dtype=np.float64)
    n = 0
    for obj in (osmium.FileProcessor(str(PBF), osmium.osm.NODE)
                .with_filter(F.IdFilter(need.tolist()))):
        got_id[n] = obj.id
        got_lat[n] = obj.location.lat
        got_lon[n] = obj.location.lon
        n += 1
    got_id, got_lat, got_lon = got_id[:n], got_lat[:n], got_lon[:n]
    order = np.argsort(got_id)
    got_id, got_lat, got_lon = got_id[order], got_lat[order], got_lon[order]
    print(f"[{elapsed()}] {n:,} resolved, {len(need) - n:,} missing "
          f"(nodes referenced across the extract boundary)", flush=True)

    def coords_for(refs):
        ids = np.frombuffer(refs, dtype=np.int64)
        pos = np.clip(np.searchsorted(got_id, ids), 0, max(len(got_id) - 1, 0))
        ok = got_id[pos] == ids
        return got_lat[pos[ok]], got_lon[pos[ok]]

    # -------------------------------------------------------------------- assemble
    lines = []
    for osm_id, kind, state, tag, service, name, refs in line_ways:
        la, lo = coords_for(refs)
        if len(la) >= 2:
            lines.append({
                "id": osm_id, "kind": kind, "state": state, "tag": tag,
                "service": service, "name": name,
                "pts": [[round(float(a), 5), round(float(b), 5)] for a, b in zip(la, lo)],
            })

    way_pubs = 0
    for tags, osm_id, refs in pub_ways:
        la, lo = coords_for(refs)
        if len(la):
            # mean of the footprint's nodes; a pub building is metres across
            pubs.append(pub_record(tags, osm_id, "w", float(la.mean()), float(lo.mean())))
            way_pubs += 1

    (RAW / "pubs.json").write_text(json.dumps(pubs), encoding="utf-8", newline="\n")
    with open(RAW / "lines.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(lines, fh)

    by_state = {}
    for p in pubs:
        by_state[p["state"]] = by_state.get(p["state"], 0) + 1
    by_line = {}
    for ln in lines:
        k = f'{ln["kind"]}/{ln["state"]}'
        by_line[k] = by_line.get(k, 0) + 1

    print(f"\n[{elapsed()}] pubs   {len(pubs):>8,}  {by_state}  ({way_pubs:,} from footprints)")
    print(f"[{elapsed()}] lines  {len(lines):>8,}  {by_line}")
    print(f"[{elapsed()}] points {sum(len(ln['pts']) for ln in lines):>8,}")


if __name__ == "__main__":
    main()
