#!/usr/bin/env python
"""Measure every pub against the lines on the ground, and build the page payload.

Reads  raw/pubs.json, raw/lines.json   (written by extract.py)
Writes payload.json                    (spliced into the page by inject.py)
       stats.json                      (the numbers quoted in the prose and REBUILD.md)

The headline question is whether pub names remember infrastructure that has gone. The
trap is that railways and pubs are both urban, so a railway-named pub sitting near a
dismantled line proves nothing on its own: dismantled lines are near everything in a
town. Two independent measures are computed:

  1. Threshold lift. Of pubs that are far from any working line (>1 km) but close to a
     dismantled one (<250 m), what share carry a railway name, against the base rate?

  2. A paired test. Each railway-named pub is matched to its nearest *other* pub, a few
     hundred metres away in the same town, and the two are compared on distance to the
     nearest dismantled line. The control sits in the same place, so urbanity, pub
     density and regional differences all cancel. A sign test over the pairs follows.

Measure 1 can be inflated by geography; measure 2 cannot. They are reported together.
"""
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

import geom
import names as nm

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

R_EARTH = 6_371_000.0
DENSIFY_M = 40.0        # interpolate line vertices to at most this spacing
DEDUPE_M = 60.0         # same name within this distance is one pub mapped twice
NEAR_M = 250.0          # "close to"
FAR_M = 1000.0          # "far from"
CAP_M = 20_000          # distances are capped before they go in the payload


def project(lat, lon):
    """Sinusoidal projection in metres. Equal-area, and locally true to within a
    fraction of a percent over the few-kilometre scales measured here."""
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    y = np.radians(lat) * R_EARTH
    x = np.radians(lon) * R_EARTH * np.cos(np.radians(lat))
    return x, y


def densify(pts):
    """Return vertices along a polyline, spaced at most DENSIFY_M apart.

    Nearest-vertex distance is then a good proxy for nearest-line distance: the worst
    case error is half the spacing on a straight run, which is 20 m, well inside the
    250 m threshold the findings use.
    """
    lat = np.array([p[0] for p in pts], dtype=np.float64)
    lon = np.array([p[1] for p in pts], dtype=np.float64)
    x, y = project(lat, lon)
    out_x, out_y = [x[0]], [y[0]]
    for i in range(1, len(x)):
        dx, dy = x[i] - x[i - 1], y[i] - y[i - 1]
        seg = math.hypot(dx, dy)
        n = int(seg // DENSIFY_M)
        for k in range(1, n + 1):
            t = k * DENSIFY_M / seg
            out_x.append(x[i - 1] + dx * t)
            out_y.append(y[i - 1] + dy * t)
        out_x.append(x[i])
        out_y.append(y[i])
    return np.array(out_x), np.array(out_y)


def load_pubs():
    pubs = json.loads((RAW / "pubs.json").read_text(encoding="utf-8"))
    for p in pubs:
        p.update(nm.parse(p["name"]))
    # dedupe: the same canonical name mapped as both a node and a building
    x, y = project([p["lat"] for p in pubs], [p["lon"] for p in pubs])
    tree = cKDTree(np.c_[x, y])
    drop = set()
    for i, j in tree.query_pairs(DEDUPE_M):
        if i in drop or j in drop:
            continue
        if pubs[i]["canon"] == pubs[j]["canon"]:
            # keep whichever record carries more tags; on a tie keep the lower id, so
            # the choice is stable across rebuilds
            def richness(p):
                return sum(1 for k in ("operator", "brewery", "start_date", "building")
                           if p.get(k))
            ri, rj = richness(pubs[i]), richness(pubs[j])
            if ri > rj:
                drop.add(j)
            elif rj > ri:
                drop.add(i)
            else:
                drop.add(j if pubs[i]["id"] <= pubs[j]["id"] else i)
    kept = [p for i, p in enumerate(pubs) if i not in drop]
    return kept, len(drop)


def load_clouds():
    """Four vertex clouds: rail/canal x open/closed, each densified and projected."""
    lines = json.loads((RAW / "lines.json").read_text(encoding="utf-8"))
    buckets = defaultdict(list)
    for ln in lines:
        buckets[(ln["kind"], ln["state"])].append(ln)
    clouds = {}
    for key, group in buckets.items():
        xs, ys = [], []
        for ln in group:
            gx, gy = densify(ln["pts"])
            xs.append(gx)
            ys.append(gy)
        pts = np.c_[np.concatenate(xs), np.concatenate(ys)]
        clouds["/".join(key)] = cKDTree(pts)
        print(f"  cloud {'/'.join(key):<14} {len(group):>7,} ways  {len(pts):>10,} vertices")
    return clouds, lines


def main():
    print("loading pubs ...")
    pubs, deduped = load_pubs()
    print(f"  {len(pubs):,} pubs ({deduped:,} duplicates merged)")

    print("building line indexes ...")
    clouds, lines = load_clouds()

    px, py = project([p["lat"] for p in pubs], [p["lon"] for p in pubs])
    pq = np.c_[px, py]

    dist = {}
    for key, tree in clouds.items():
        d, _ = tree.query(pq, k=1)
        dist[key] = d
        print(f"  {key:<14} median {np.median(d)/1000:7.2f} km   min {d.min():6.0f} m")

    d_rail_open = dist.get("rail/open")
    d_rail_closed = dist.get("rail/closed")
    d_canal_open = dist.get("canal/open")
    d_canal_closed = dist.get("canal/closed")

    remembers = np.array([p.get("remembers") or "" for p in pubs])
    is_rail_named = remembers == "rail"
    is_canal_named = remembers == "canal"

    stats = {
        "pubs_total": len(pubs),
        "pubs_duplicates_merged": deduped,
        "pubs_open": int(sum(1 for p in pubs if p["state"] == "open")),
        "pubs_former": int(sum(1 for p in pubs if p["state"] == "former")),
        "rail_named": int(is_rail_named.sum()),
        "canal_named": int(is_canal_named.sum()),
        "rail_open_ways": sum(1 for l in lines if l["kind"] == "rail" and l["state"] == "open"),
        "rail_closed_ways": sum(1 for l in lines if l["kind"] == "rail" and l["state"] == "closed"),
        "canal_closed_ways": sum(1 for l in lines if l["kind"] == "canal" and l["state"] == "closed"),
    }

    # ---------------------------------------------------------- measure 1: lift
    def lift(named_mask, d_open, d_closed, label):
        orphan = (d_open > FAR_M) & (d_closed < NEAR_M)   # far from live, close to dead
        base = named_mask.mean()
        among = named_mask[orphan].mean() if orphan.sum() else float("nan")
        res = {
            "orphan_sites": int(orphan.sum()),
            "base_rate": float(base),
            "rate_at_orphan_sites": float(among),
            "lift": float(among / base) if base else float("nan"),
            "named_far_from_live": int((named_mask & (d_open > FAR_M)).sum()),
            "named_far_from_live_but_near_dead": int((named_mask & orphan).sum()),
            "others_far_from_live": int((~named_mask & (d_open > FAR_M)).sum()),
            "others_far_from_live_but_near_dead": int((~named_mask & orphan).sum()),
        }
        print(f"\n[{label}] measure 1, threshold lift")
        print(f"  base rate of {label}-named pubs        {base*100:6.2f}%")
        print(f"  at sites far from live, near dead line {among*100:6.2f}%"
              f"   ({res['orphan_sites']:,} such sites)")
        print(f"  lift x{res['lift']:.2f}")
        return res

    stats["rail_lift"] = lift(is_rail_named, d_rail_open, d_rail_closed, "rail")
    if d_canal_open is not None and d_canal_closed is not None:
        stats["canal_lift"] = lift(is_canal_named, d_canal_open, d_canal_closed, "canal")

    # ------------------------------------------------- measure 2: paired control
    def paired(named_mask, d_closed, label):
        """Each named pub against its nearest other pub, on distance to a dead line."""
        tree_all = cKDTree(pq)
        idx_named = np.flatnonzero(named_mask)
        # k=8 so we can skip the pub itself and any other same-family pub nearby
        dd, ii = tree_all.query(pq[idx_named], k=8)
        pairs = []
        for row, src in enumerate(idx_named):
            for col in range(8):
                cand = ii[row, col]
                if cand == src or named_mask[cand]:
                    continue
                pairs.append((src, cand, dd[row, col]))
                break
        a = np.array([p[0] for p in pairs])
        b = np.array([p[1] for p in pairs])
        sep = np.array([p[2] for p in pairs])
        da, db = d_closed[a], d_closed[b]
        closer = int((da < db).sum())
        further = int((da > db).sum())
        n = closer + further
        # two-sided sign test, normal approximation (n is in the hundreds)
        z = (closer - n / 2) / math.sqrt(n / 4) if n else float("nan")
        res = {
            "pairs": len(pairs),
            "median_separation_m": float(np.median(sep)),
            "named_median_m": float(np.median(da)),
            "control_median_m": float(np.median(db)),
            "named_closer": closer,
            "control_closer": further,
            "ties": int(len(pairs) - n),
            "sign_test_z": float(z),
            "named_within_near": float((da < NEAR_M).mean()),
            "control_within_near": float((db < NEAR_M).mean()),
        }
        print(f"\n[{label}] measure 2, paired against the nearest other pub")
        print(f"  {len(pairs):,} pairs, median separation {res['median_separation_m']:.0f} m")
        print(f"  median distance to the line:  named {res['named_median_m']:7.0f} m"
              f"   control {res['control_median_m']:7.0f} m")
        print(f"  named closer in {closer:,} pairs, control closer in {further:,}"
              f"   (sign test z = {z:+.1f})")
        print(f"  within {NEAR_M:.0f} m of a dead line: named {res['named_within_near']*100:5.1f}%"
              f"   control {res['control_within_near']*100:5.1f}%")
        return res, da, db

    stats["rail_paired"], rail_named_dead, rail_control_dead = paired(
        is_rail_named, d_rail_closed, "rail")
    if d_canal_closed is not None:
        stats["canal_paired"] = paired(is_canal_named, d_canal_closed, "canal")[0]

    # a falsification check: the same paired test against LIVE lines. If railway names
    # simply mark "anywhere near metal", the live-line gap should be as large.
    stats["rail_paired_live"] = paired(is_rail_named, d_rail_open, "rail-vs-live")[0]

    # measure 3, added when the build was finished: the paired test away from working
    # lines. Near a live station two things manufacture a dead-line gap that has nothing
    # to do with memory: a "Station Hotel" sits by the station, and the station is ringed
    # by lifted sidings and yards mapped as dismantled track. Restricting both members of
    # every pair to pubs more than FAR_M from any open line removes both. What is left is
    # the question the page asks: where the trains have gone, does the name still sit by
    # the trackbed?
    def paired_far(named_mask, d_open, d_closed, label):
        sub = np.flatnonzero(d_open > FAR_M)
        sub_named = named_mask[sub]
        tree_sub = cKDTree(pq[sub])
        idx = np.flatnonzero(sub_named)
        if not len(idx):
            return {"pairs": 0}
        dd, ii = tree_sub.query(pq[sub][idx], k=min(8, len(sub)))
        a, b, sep = [], [], []
        for row, src in enumerate(idx):
            for col in range(ii.shape[1]):
                cand = ii[row, col]
                if cand == src or sub_named[cand]:
                    continue
                a.append(sub[src]); b.append(sub[cand]); sep.append(dd[row, col])
                break
        a, b, sep = np.array(a), np.array(b), np.array(sep)
        da, db = d_closed[a], d_closed[b]
        closer, further = int((da < db).sum()), int((da > db).sum())
        n = closer + further
        z = (closer - n / 2) / math.sqrt(n / 4) if n else float("nan")
        res = {
            "pubs_far_from_live": int(len(sub)),
            "pairs": int(len(a)),
            "median_separation_m": float(np.median(sep)),
            "named_median_m": float(np.median(da)),
            "control_median_m": float(np.median(db)),
            "named_closer": closer,
            "control_closer": further,
            "ties": int(len(a) - n),
            "sign_test_z": float(z),
            "named_within_near": float((da < NEAR_M).mean()),
            "control_within_near": float((db < NEAR_M).mean()),
            "named_idx": a.tolist(),
            "control_idx": b.tolist(),
        }
        print(f"\n[{label}] measure 3, paired, both pubs > {FAR_M:.0f} m from any open line")
        print(f"  {len(sub):,} such pubs, {len(a):,} pairs, median separation {res['median_separation_m']:.0f} m")
        print(f"  median distance to a dead line:  named {res['named_median_m']:7.0f} m"
              f"   control {res['control_median_m']:7.0f} m")
        print(f"  named closer in {closer:,} pairs, control closer in {further:,}   (z = {z:+.1f})")
        print(f"  within {NEAR_M:.0f} m of a dead line: named {res['named_within_near']*100:5.1f}%"
              f"   control {res['control_within_near']*100:5.1f}%")
        return res

    stats["rail_paired_far"] = paired_far(is_rail_named, d_rail_open, d_rail_closed, "rail-far")
    # the same test with only the two words nobody uses for anything else: a pub whose
    # name contains RAILWAY or STATION. If the result leaned on junction, midland or the
    # locomotive names, it would weaken here.
    is_core = np.array([p.get("remembers") == "rail" and
                        bool({"railway", "railways", "station"} & set(p["canon"].split()))
                        for p in pubs])
    stats["rail_core_paired_far"] = paired_far(is_core, d_rail_open, d_rail_closed,
                                               "rail-far, railway/station only")

    # the placebo: the same restricted test on a vocabulary with no reason to sit by a
    # railway, the heraldic colour+animal signs (Red Lion, White Hart). A gap here would
    # mean the restriction or the pairing, not the name, produces it.
    is_heraldic = np.array([p.get("template") == "colour+animal" for p in pubs])
    stats["heraldic_paired_far"] = paired_far(is_heraldic, d_rail_open, d_rail_closed,
                                              "heraldic-far (placebo)")
    # extraction names are NOT a placebo (coalfields were laced with mineral railways,
    # most now lifted), but they are reported for what they show
    is_extr_named = remembers == "extraction"
    stats["extraction_paired_far"] = paired_far(is_extr_named, d_rail_open, d_rail_closed,
                                                "extraction-far")

    # ---------------------------------------------------------------- vocabulary
    canon_counts = Counter(p["canon"] for p in pubs)
    stats["distinct_names"] = len(canon_counts)
    stats["top_names"] = canon_counts.most_common(60)
    stats["once_only"] = int(sum(1 for c in canon_counts.values() if c == 1))

    grid = Counter()
    for p in pubs:
        if p.get("template") == "colour+animal":
            grid[(p["colour"], p["animal"])] += 1
    stats["colour_animal_cells"] = len(grid)
    stats["colour_animal_total"] = int(sum(grid.values()))
    stats["colour_animal_top"] = [list(k) + [v] for k, v in grid.most_common(40)]

    templates = Counter(p.get("template") or "unclassified" for p in pubs)
    stats["templates"] = templates.most_common()

    arms = Counter(p["arms"] for p in pubs if p.get("arms"))
    stats["arms_total"] = int(sum(arms.values()))
    stats["arms_named_trade"] = int(sum(v for k, v in arms.items() if k in nm.TRADES))
    stats["arms_top"] = arms.most_common(40)

    pairs_c = Counter(tuple(p["pair"]) for p in pubs if p.get("pair"))
    stats["pairs_top"] = [list(k) + [v] for k, v in pairs_c.most_common(40)]

    (HERE / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8", newline="\n")

    # ----------------------------------------------------------------- geometry
    # Two decimations of the same lines. The national map is about a kilometre to the
    # pixel, so 300 m is already finer than it can show; the close-up panel needs
    # better, but only for lines near a pub whose name is about infrastructure, which
    # bounds the cost.
    print("\nsimplifying line geometry ...")
    focus = np.flatnonzero(np.isin(remembers, ["rail", "canal", "extraction"]))
    focus_tree = cKDTree(pq[focus]) if len(focus) else None

    def encode_set(eps, min_len, only_near=None):
        out = {}
        kept = pts = 0
        for ln in lines:
            key = f'{ln["kind"]}/{ln["state"]}'
            if only_near is not None:
                if focus_tree is None:
                    continue
                lx, ly = geom.project([p[0] for p in ln["pts"]], [p[1] for p in ln["pts"]])
                d, _ = focus_tree.query(np.c_[lx, ly], k=1)
                if d.min() > only_near:
                    continue
            simp = geom.simplify(ln["pts"], eps_m=eps, min_len_m=min_len)
            if not simp:
                continue
            out.setdefault(key, []).append(geom.encode(simp))
            kept += 1
            pts += len(simp)
        print(f"  eps={eps:>4.0f}m  {kept:>7,} lines  {pts:>9,} points  "
              f"{sum(len(s) for v in out.values() for s in v)/1e6:5.2f} MB of polyline")
        return out

    geom_map = encode_set(300.0, 400.0)
    geom_near = encode_set(40.0, 100.0, only_near=1200.0)

    # ------------------------------------------------------------------ payload
    name_list = sorted(canon_counts)
    name_idx = {n: i for i, n in enumerate(name_list)}

    def cap(d):
        return np.minimum(np.nan_to_num(d, nan=CAP_M), CAP_M).round().astype(int).tolist()

    payload = {
        # the date the extract was downloaded, which is what the numbers describe
        "built": __import__("datetime").date.fromtimestamp(
            (RAW / "great-britain-latest.osm.pbf").stat().st_mtime).strftime("%-d %B %Y")
            if sys.platform != "win32" else
            __import__("datetime").date.fromtimestamp(
            (RAW / "great-britain-latest.osm.pbf").stat().st_mtime).strftime("%#d %B %Y"),
        "stats": stats,
        "names": name_list,
        "geom": {"map": geom_map, "near": geom_near},
        # the paired controls, so the page can draw their curve without re-deriving the
        # pairing (nearest-neighbour indices are not otherwise shipped)
        "control_dead": np.minimum(rail_control_dead, CAP_M).round().astype(int).tolist(),
        "pubs": {
            "display": [p["name"] for p in pubs],
            "canon": [name_idx[p["canon"]] for p in pubs],
            "lat": [round(p["lat"], 5) for p in pubs],
            "lon": [round(p["lon"], 5) for p in pubs],
            "state": [0 if p["state"] == "open" else 1 for p in pubs],
            "template": [p.get("template") or "" for p in pubs],
            "colour": [p.get("colour") or "" for p in pubs],
            "animal": [p.get("animal") or "" for p in pubs],
            "arms": [p.get("arms") or "" for p in pubs],
            "trade_group": [p.get("trade_group") or "" for p in pubs],
            "remembers": [p.get("remembers") or "" for p in pubs],
            "d_rail_open": cap(d_rail_open),
            "d_rail_closed": cap(d_rail_closed),
            "d_canal_open": cap(d_canal_open) if d_canal_open is not None else None,
            "d_canal_closed": cap(d_canal_closed) if d_canal_closed is not None else None,
        },
    }
    out = HERE / "payload.json"
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8", newline="\n")
    raw_mb = out.stat().st_size / 1e6
    gz_mb = len(gzip.compress(out.read_bytes(), 9)) / 1e6
    print(f"\npayload.json {raw_mb:.1f} MB raw, {gz_mb:.1f} MB gzipped")


if __name__ == "__main__":
    sys.exit(main())
