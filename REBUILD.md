# Rebuilding Last Orders

Enough to reproduce this project from nothing: a shell, Python, and about an hour, most of
which is one file downloading and then being read twice.

## 1. What is being built

One self-contained HTML page about British pub names, in four parts.

A pub name in Britain is rarely an invention; it is assembled from a short vocabulary.
The page pulls every named pub out of OpenStreetMap, parses each name into its slots
(colour + animal, trade + Arms, number + object, A and B), and then measures each pub
against the railway and canal geometry around it - the lines that still carry traffic and
the lines that have been lifted.

**The finding the page exists to show:** where the trains have gone, the railway names
stayed. Of the 127 railway-named pubs more than a kilometre from any working line, 105 stand
nearer a dismantled line than their nearest neighbour does (also more than a kilometre from a
working line): medians 105 m against 373 m, sign test z = +7.4. With only the words Railway
and Station it is 82 of 96. The same test on the heraldic colour-plus-animal signs is null
(662 of 1,359, z = -0.9). Britain lifted roughly a third of its network in the twenty years
after 1955, and the pub names did not follow.

**History of this file.** It was first written on 2026-10-05 by the session that designed the
pipeline, before any of it had run, and it predicted that the paired test against *open*
lines would show no gap. When the build was finished on 2026-10-13 the opposite came out: the
gap against open lines is the largest of all. §3 now says why, and measure three was added to
replace the check that failed.

The trap, and the reason there are two measures, is that railways and pubs are both urban.
In a town a dismantled line is near everything, so "railway pub sits near a dead line" is
not evidence on its own. See §3.

## 2. Data

One source, one file. OpenStreetMap, via the Geofabrik Great Britain extract:

```
https://download.geofabrik.de/europe/great-britain-latest.osm.pbf     ~2.1 GB
```

ODbL. Attribution ("© OpenStreetMap contributors") is in the page footer and in
`meta.json`.

**Do not use Overpass for this.** It was the first route tried and it is the wrong one:
the public mirrors were timing out under load (`overpass-api.de` returned a dispatcher
timeout, two others never answered), and the mirrors that did answer were serving data
weeks stale (timestamps of 2026-05-31 and 2026-07-15 while the Geofabrik extract was
current). One download is both faster and reproducible.

What is extracted, and the tags that matter:

| layer | tags |
|---|---|
| pubs, open | `amenity=pub` with a `name` |
| pubs, former | `disused:amenity=pub` and the `abandoned:` / `was:` / `former:` / `demolished:` / `razed:` spellings, with a `name` |
| railway, live | `railway=rail\|light_rail\|narrow_gauge\|subway\|tram\|monorail\|funicular\|preserved\|miniature` |
| railway, dead | `railway=abandoned\|dismantled\|razed\|disused\|demolished\|removed`, plus `disused:railway=*` and the other lifecycle-prefix spellings |
| canal, live | `waterway=canal` |
| canal, dead | `disused:waterway=canal` and siblings, or `waterway=canal` with `disused=yes` |

Quirks that will bite:

* **Pubs are mapped two ways** - as a node, or as a building outline. Take the mean of the
  outline's nodes as the position, then merge records within 60 m that share a canonical
  name, or every such pub is counted twice.
* **Names need folding before they can be counted.** The same house appears as
  `The Miner's Arms`, `Miners Arms`, `Miners' Arms` and `The Miners Arms (Inn)`. Strip the
  article, strip a trailing house word (Inn, Hotel, Tavern, PH, Vaults...), drop the
  possessive apostrophe. Without this the name ranking is nonsense.
* **`railway=razed` is not standard** but exists in the data; `razed:railway=*` is the
  preferred spelling. Accept both.
* **Relations are skipped.** A handful of pubs are multipolygons; they have no geometry
  assembled here and are dropped.

## 3. Processing decisions, and why

**Distance is nearest-vertex, not perpendicular-to-segment.** Lines are densified so that
no two consecutive vertices are more than 40 m apart, then the nearest vertex is taken.
Worst-case error is half the spacing, 20 m, on a straight run - comfortably inside the
250 m threshold the findings use, and far cheaper than segment distance over several
million vertices.

**Projection is sinusoidal** (`x = R·λ·cos φ`, `y = R·φ`), equal-area and locally true to
a fraction of a percent at these scales. Britain spans 50°N to 59°N, so a plain
lat/lon KD-tree would distort north-south distances by a third.

**The vocabulary is hand-written**, in `src/names.py`. Two entries were wrong and were
fixed after reading the matched names: *mallard* (meant for the A4 locomotive; nearly every
pub called The Mallard is the duck) was removed, and *grand junction* (the Grand Junction
Canal) moved from the railway words to the canal words and is tested first. This is a judgement, not an
ontology: a name matches a template or it falls through, and the fall-through share is
published on the page rather than tuned away. Infrastructure words are grouped as `rail`,
`canal` and `extraction`, and each group is tested against its own kind of line.

**Three measures of the finding, because the first two are not safe:**

1. *Threshold lift.* Take sites more than 1 km from a live line but within 250 m of a dead
   one, and ask what share of pubs there are railway-named, against the base rate. It
   gives a big number and it is confounded: those sites are concentrated in old industrial
   districts where dismantled lines and railway pubs are both common for unrelated
   reasons.
2. *Paired control.* Each railway-named pub is matched to its nearest **other** pub - a
   median of a few hundred metres away, usually the same street - and the two are compared
   on distance to the nearest dismantled line. A sign test over the pairs follows. The
   control sits in the same town, the same era, the same industrial history, so whatever
   urbanity does to the measurement it does to both.

**The check that was meant to fail, and did not.** The plan was to run the identical paired
test against lines that are still open and expect no gap. Wrong answer (what this file said
before the build ran): "a rebuild that finds a large gap on live lines too has a bug". Right
answer: the live-line gap is real and is the largest of all (441 of 632 pairs, 100 m against
300 m, z = +9.9), because a Station Hotel stands by a station and most stations still have
trains. Worse, working stations are ringed by lifted sidings and yards mapped as dismantled
track, so measure 2's dead-line gap can be manufactured by live stations. Measure 2 is kept
on the page, labelled as the check that did not do its job.

3. *Paired, away from the working lines* (added 2026-10-13). Keep only pubs more than 1 km
   from any open line (17,129). Pair each railway-named pub among them with its nearest
   non-railway-named pub from the same subset, and compare distance to a dismantled line.
   No live station, no working yard. This carries the headline. Two checks ride on it:
   * *strict vocabulary*: only names containing RAILWAY or STATION;
   * *placebo*: the identical test on colour+animal names (Red Lion, White Hart). It must be
     null. Extraction names are **not** a placebo (coalfields were laced with mineral lines)
     and are reported separately (47 of 84, z = +1.1).
   The page withholds the headline if measure 3 or the strict version falls below z = 3 or
   the placebo exceeds |z| = 2. The page recomputes all three from the shipped pair indices
   and the distances rounded to whole metres, which turns a handful of near-ties into ties:
   the placebo reads 660 of 1,356 on the page against 662 of 1,359 here.

**Direction of the remaining bias.** Mapping of old trackbeds in OSM is enthusiastic but
incomplete, and an unmapped trackbed makes a railway pub look *further* from a dead line
than it really is. The bias runs against the finding, not for it.

## 4. The page

Cream signboard, oxblood and brass, one deep railway green. Green always means a line
trains still run on; oxblood always means a line that is gone, and also every finding.
Playfair Display for display type (painted-sign didone), IBM Plex Sans and Mono for
everything else. Light and dark both defined.

Four sections:

1. **The grammar of the sign.** The colour × animal grid as a heatmap - mostly empty,
   which is the point: the vocabulary is heraldic, so there are Red Lions everywhere and
   almost no Red Lambs. Clicking a cell filters the map. Beside it, the trades behind
   *Arms* and the commonest *A and B* pairs, and a table of template shares including the
   unclassified remainder.
2. **Every pub, and every line.** A canvas map of all pubs with the rail and canal
   geometry behind them. No basemap and no coastline: the shape of Britain is the pubs.
   Drag to pan, scroll to zoom, click a pub to open its sign - the parsed slots, its
   distances, and a 3 km close-up drawn from finer geometry.
3. **What the name remembers.** The two measures, as three-card verdicts; a dumbbell of
   named-vs-control medians for dead and live lines; cumulative distance curves for
   railway-named pubs, their paired controls, and everything else; then the canals on a
   smaller sample.
4. **Method.** What the page cannot say, including OSM's volunteered coverage.

Geometry ships as Google encoded polylines - about 4 bytes a point against 20 as JSON
numbers - in two decimations: 300 m tolerance for the national map (finer than a
kilometre-to-the-pixel canvas can show), and 40 m for lines within 1.2 km of an
infrastructure-named pub, for the close-up panel.

## 5. Verification

Figures from the build of 2026-10-05, against the Geofabrik extract current that day.
OpenStreetMap is edited continuously, so a later rebuild will drift - but not by much, and
not in the shape of the result. `src/stats.json` carries the full set.

Built 2026-10-13 from the Geofabrik extract downloaded 2026-10-05 (2,182,060,956 bytes).
Extraction took 441 s on this run (pass 1 416 s, pass 2 13 s), far faster than the first
session measured.

| quantity | value |
|---|---|
| pubs extracted / after merging duplicates | 39,157 / 38,986 (171 merged) |
| open / former | 37,434 / 1,552 |
| pub records from building outlines | 22,395 |
| railway ways open / dismantled | 102,068 / 33,258 |
| canal ways open / disused | 8,488 / 397 |
| distinct canonical names / names used once | 16,999 / 14,006 |
| railway-named / canal-named pubs | 632 / 257 |
| measure 1: base rate, rate at orphaned sites, lift | 1.62%, 4.48% of 1,899 sites, x2.76 |
| measure 2 (dead lines): pairs, named closer, medians, z | 632, 409 vs 223, 364 m vs 503 m, +7.4 |
| live-line check: named closer, medians, z | 441 vs 191, 100 m vs 300 m, +9.9 |
| measure 3: pubs far from live, pairs, named closer, medians, z | 17,129, 127, 105 vs 22, 105 m vs 373 m, +7.4 |
| measure 3 within 250 m of a dead line | 66.9% vs 42.5% |
| strict vocabulary (Railway/Station) | 82 vs 14 of 96, 87 m vs 294 m, +6.9 |
| placebo (colour+animal) | 662 vs 697 of 1,359, 1,981 m vs 1,816 m, -0.9 |
| canal paired test | 134 vs 123 of 257, medians 15.0 km vs 14.9 km, +0.7 (null: too few disused canals mapped) |

Recognisable checkpoints, which catch a parse error instantly:

| checkpoint | value |
|---|---|
| commonest name | Red Lion, 535 (547 counting every colour+animal Red Lion spelling) |
| next | Crown 468, Royal Oak 424, White Hart 304, Plough 284, **Railway 274** |
| colour+animal combinations / pubs | 107 / 2,372 |
| commonest Arms | Kings 201, Masons 75, Farmers 66, Carpenters 63, Butchers 60 |
| commonest A and B | Rose and Crown 226, Coach and Horses 128, Fox and Hounds 122, George and Dragon 122 |
| template shares | unclassified 29,632; x+Arms 3,304; A and B 2,928; colour+animal 2,372; number+object 750 |
| measure 3, nearest pairs | The Railway 13 m from a dismantled line (its neighbour 138 m); The Old Station House Inn 16 m (459 m) |

## 6. What the page must say about itself

* OpenStreetMap is volunteered. A pub is on the map because somebody mapped it; coverage
  is good in Britain but not uniform, and the count will not match the licensing figures.
* "Dismantled" is OSM's word, not a historical record, and trackbed mapping is incomplete.
* Distances are straight-line to the nearest line, not along a road.
* The name vocabulary is a hand-written judgement, and the unclassified share is published.
* The paired test is a sign test, not a model: it asks only which of two pubs is closer.
* Nothing is fetched while the page is read except the visit counter.
