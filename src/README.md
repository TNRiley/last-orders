# src - the Last Orders pipeline

Four scripts, run in order. Nothing here needs an API key, and nothing is fetched at page
load except the visit counter.

```bash
# 0. the data: one 2.1 GB OpenStreetMap extract of Great Britain
mkdir -p raw
curl -L -o raw/great-britain-latest.osm.pbf \
  https://download.geofabrik.de/europe/great-britain-latest.osm.pbf

python extract.py     # raw/pubs.json, raw/lines.json      (two passes over the pbf)
python analyse.py     # payload.json, stats.json
python inject.py      # ../index.html, wrapped and breadcrumbed
```

`pip install osmium numpy scipy` covers the dependencies. On Windows the interpreter is
`python`, not `python3`.

| file | what it does |
|---|---|
| `extract.py` | pulls named pubs and railway/canal geometry out of the pbf |
| `names.py` | the hand-written vocabulary - colours, animals, trades, infrastructure - and the name parser |
| `geom.py` | Ramer-Douglas-Peucker simplification and encoded-polyline packing for the map |
| `analyse.py` | distances, the two measures of the finding, the aggregates, the payload |
| `inject.py` | splices `payload.json` into `template.html`, then re-runs the catalog tools |

## Two things that cost real time here

**`with_locations()` is a trap on an extract this size.** It is the documented way to get
way geometry out of pyosmium, and it writes one index entry for every node in the file -
about 130 million of them. Measured on this machine: roughly 2 % of the file in five
minutes, with 17 seconds of CPU against five minutes of wall clock, i.e. pure disk
thrash. `extract.py` instead collects node ids from the ways it wants and resolves them in
a second pass behind an `IdFilter`, which libosmium applies in C++.

**Filter on key=value, not on key.** A `KeyFilter("waterway")` surfaces every stream,
ditch and drain in Britain to Python. The single `TagFilter` of ~140 explicit pairs keeps
all of that rejection inside libosmium.

Both passes are I/O-bound rather than CPU-bound - on this PC the pbf streamed at about
1 MB/s with real-time virus scanning in the way, so a pass took on the order of fifteen
minutes while using well under a minute of CPU. That is the machine, not the code.

## Re-running it

`raw/` is gitignored: the pbf is 2.1 GB and the two intermediates run to hundreds of MB.
Everything in `raw/` is reproducible from the Geofabrik URL above, though the numbers will
drift as OpenStreetMap is edited - the verification table in `../REBUILD.md` records what
this build measured and on which date.
