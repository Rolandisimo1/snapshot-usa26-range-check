# Snapshot USA Range & Taxonomy Check — 2026 survey and Lewis & Clark Resurvey

A single self-contained page (`docs/index.html`) for GitHub Pages. A switch at the top toggles between
**Snapshot USA 2026** and the **Lewis & Clark Resurvey**. Below it are the same 12 genus/group tabs as the
2025 Snapshot USA ID dashboard (range maps, iNaturalist presence boundaries, ID tips), plus a
**Range flags** tab that lists every wild-mammal identification found outside its known range.

Modelled on https://rolandisimo1.github.io/snapshot-usa-wildlife-dashboard/usa_dashboard.html.

## Publish

1. Push this folder to GitHub.
2. Under Settings → Pages, choose *Deploy from branch*, `main`, folder `/docs`.
3. Links can point at a project and tab, e.g. `index.html#lc/Sciurus` or `index.html#ss26/__flags`.

## Rebuild

```
python scripts/build_range_check.py   # detections -> range statuses (outputs/*.csv, dashboard_payload.json)
python scripts/build_dashboard.py     # -> docs/index.html
```

Requires geopandas, shapely, pyogrio and pandas. Inputs are read from absolute paths at the top of
`build_range_check.py`:

- Camera data: `data_in/ss_usa26` and `data_in/ss_lewis_clark` (Wildlife Insights exports).
- IUCN mammal ranges: `geospatialdata/mammalranges/data_0.shp`.
- Fleet-34 iNaturalist presence grids: `geospatialdata/north_american_mammal_ranges/fleet34_isdm/grids_100km`.
- Under `data_raw/`, which is not committed:
  - the 2025 dashboard HTML, the source of the display polygons, iNaturalist boundaries and ID tips;
  - MDD v2.5 (Zenodo 10.5281/zenodo.21654811).

## Method

- **Names.** Every camera name is resolved to an MDD v2.5 species ID (exact match, or full-binomial synonym match).
  IUCN polygons are joined on that MDD ID, not on the name string.
- **Distance.** For each deployment × taxon, the distance in km (EPSG:5070) is measured to the nearest edge of the
  species' range. IUCN ranges keep extant, probably extant and possibly extant areas of native, reintroduced,
  introduced, uncertain or assisted origin; vagrant areas are excluded. Where an iNaturalist presence boundary
  exists, the nearer of the two sources is used. Boundaries exist for the 12 tab groups and the fleet-34 species.
- **Statuses.**
  - *In range*: ≤ 25 km.
  - *Near edge*: 25–100 km.
  - *Outside known range*: > 100 km, or a species with no range anywhere in the Americas and no US record in MDD.
- **Special cases**, each listed explicitly in `build_range_check.py`:
  - *Outdated WI name*: names now split in MDD are relabeled and checked under the MDD species:
    *Dasypus novemcinctus* → *D. mexicanus*; *Urva javanica* → *U. auropunctata* (Puerto Rico).
  - *Introduced/managed (verify)*: naturalized exotics with no IUCN US polygon, inside their documented states
    (chital and nilgai TX; sika MD/VA/TX/OK/WI), plus feral hog, nutria, black and Norway rat, and managed bison.
    Outside their documented states they count as outside.
  - *Split species without their own IUCN polygon* use the parent's pre-split range: *Glaucomys oregonensis*,
    *Martes caurina*, *Mustela richardsonii*, *Otospermophilus douglasii*.
  - *Genus not in US*: genus-level IDs of genera with no US species, e.g. *Capreolus*, *Muntiacus*, *Macaca*,
    *Tragelaphus*. Genera of domestic and introduced species are exempt.
  - Family-level IDs are not checked. Domestic animals and humans are excluded.
- **Map arrays.** Arrays are subprojects shown at the mean deployment location. Deployments with no subproject are
  grouped by placename. Duplicate deployment IDs keep the first location.

## Outputs

- `outputs/flag_review.csv`: flagged rows, one per project × array × taxon, with example deployment and sequence IDs.
- `outputs/array_taxon_status.csv`: all array × taxon statuses.
- `outputs/detections_range_check.csv`: deployment × taxon detail.

## Known limitations

- IUCN polygons lag recolonisations and expansions, e.g. moose, black bear, raccoon in the Great Basin. Some
  *outside* flags are real animals, so the distance column helps triage.
- The iNaturalist boundaries were built for the 2025 dashboard (tab groups) and the fleet-34 ISDM.
  No other species has a second source.
