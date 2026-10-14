#!/usr/bin/env python
"""Line simplification and compact encoding for the map layer.

The page draws Britain's railways and canals, live and dead, behind the pubs. Full OSM
geometry is far more than the map can use: at national scale the canvas is about a
kilometre to the pixel, so anything finer than a few hundred metres is invisible. Lines
are therefore reduced with Ramer-Douglas-Peucker and written as delta-encoded varint
strings (the Google encoded-polyline scheme), which costs three to five bytes a point
instead of twenty as JSON numbers.
"""
import math

import numpy as np

R_EARTH = 6_371_000.0


def project(lat, lon):
    """Sinusoidal projection in metres - equal-area, locally true at these scales."""
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    return (np.radians(lon) * R_EARTH * np.cos(np.radians(lat)),
            np.radians(lat) * R_EARTH)


def rdp_mask(x, y, eps):
    """Ramer-Douglas-Peucker, iterative so long lines cannot blow the stack."""
    n = len(x)
    if n < 3:
        return np.ones(n, dtype=bool)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        px, py = x[i], y[i]
        qx, qy = x[j], y[j]
        dx, dy = qx - px, qy - py
        seg = math.hypot(dx, dy)
        xs = x[i + 1:j]
        ys = y[i + 1:j]
        if seg == 0.0:
            d = np.hypot(xs - px, ys - py)
        else:
            d = np.abs(dy * (xs - px) - dx * (ys - py)) / seg
        k = int(np.argmax(d))
        if d[k] > eps:
            k += i + 1
            keep[k] = True
            stack.append((i, k))
            stack.append((k, j))
    return keep


def length_m(x, y):
    if len(x) < 2:
        return 0.0
    return float(np.hypot(np.diff(x), np.diff(y)).sum())


def simplify(pts, eps_m=300.0, min_len_m=400.0):
    """Simplify one polyline. Returns [[lat, lon], ...] or None if too short to matter."""
    lat = np.array([p[0] for p in pts], dtype=np.float64)
    lon = np.array([p[1] for p in pts], dtype=np.float64)
    x, y = project(lat, lon)
    if length_m(x, y) < min_len_m:
        return None
    m = rdp_mask(x, y, eps_m)
    return list(zip(lat[m].tolist(), lon[m].tolist()))


def encode(points, precision=5):
    """Google encoded-polyline. points is an iterable of (lat, lon)."""
    factor = 10 ** precision
    out = []
    prev_lat = prev_lon = 0
    for lat, lon in points:
        ilat = int(round(lat * factor))
        ilon = int(round(lon * factor))
        for delta in (ilat - prev_lat, ilon - prev_lon):
            v = ~(delta << 1) if delta < 0 else (delta << 1)
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        prev_lat, prev_lon = ilat, ilon
    return "".join(out)


def decode(s, precision=5):
    """Inverse of encode(), used only by the self-test below."""
    factor = 10 ** precision
    out = []
    i = 0
    lat = lon = 0
    while i < len(s):
        for which in range(2):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if which == 0:
                lat += delta
            else:
                lon += delta
        out.append((lat / factor, lon / factor))
    return out


if __name__ == "__main__":
    # round-trip check, and a simplification sanity check on a synthetic wiggle
    pts = [(54.0 + 0.001 * i, -1.5 + 0.0013 * i + 0.0002 * math.sin(i)) for i in range(400)]
    enc = encode(pts)
    back = decode(enc)
    err = max(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(pts, back))
    simp = simplify([list(p) for p in pts], eps_m=300.0)
    print(f"{len(pts)} points -> {len(enc)} chars ({len(enc)/len(pts):.1f} per point), "
          f"round-trip error {err:.2e} deg")
    print(f"simplified to {len(simp)} points at 300 m tolerance")
