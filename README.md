# 🍺 Last Orders

**Where the trains have gone, the railway names stayed: of the 127 railway-named pubs more than a kilometre from any working line, 105 stand nearer the lifted trackbed than the pub next door.**

→ **[Open it](https://tnriley.github.io/last-orders/)**

Every named pub in Great Britain (38,986 of them, from OpenStreetMap) taken apart into the slots its name is built from, colour and animal, trade and Arms, A and B, and measured against every railway and canal on the ground. Railway is the sixth commonest pub name in the country. The test that was meant to prove railway names remember dead lines failed: railway pubs sit even closer to lines that still run, because a Station Hotel stands by a station. So the working railways were taken out of the picture: among pubs more than a kilometre from any open line, the railway-named one is nearer the old trackbed than its neighbour in 105 of 127 pairs, 82 of 96 using only the words Railway and Station, while Red Lions and White Harts in the same country show no pull at all.

## Running it

One self-contained HTML file. No build step, no server, no network access at runtime — open `index.html` in a browser, or serve the directory with any static host.

```bash
python3 -m http.server 8000   # then visit http://localhost:8000
```

## Rebuilding it from scratch

[REBUILD.md](REBUILD.md) is written for an LLM with a shell and nothing else: the data sources and their quirks, the processing decisions, the page's structure and interactions, and a table of expected values to check the result against.

## Source

The full build pipeline is in [`src/`](src/), with a README describing how to regenerate the page from scratch.

## Data

- **[OpenStreetMap, Great Britain extract from Geofabrik (great-britain-latest.osm.pbf, 2.1 GB, downloaded 2026-10-05): every pub, and every railway and canal, open or disused. © OpenStreetMap contributors.](https://download.geofabrik.de/europe/great-britain.html)** — ODbL 1.0

Every figure on the page is computed from the data shipped with it. Check the page's own methods panel for how each number is derived and where it should not be pushed.

## Built with

Python, pyosmium, SciPy KD-trees, vanilla JS, canvas, encoded polylines, gzip + base64 payload.

## Licence

Code is MIT (see [LICENSE](LICENSE)). Data keeps the licence of its source, listed above.

---

Part of [Quick Projects](https://github.com/TNRiley/quick-projects) — one self-contained thing, built in one session. First published 2026-10-13.
