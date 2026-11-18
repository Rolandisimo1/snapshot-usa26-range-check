"""Range check of Snapshot USA camera-trap identifications (2026 survey + Lewis & Clark resurvey).

Inputs
  data_in/ss_usa26/{ssusa_deployments,ssusa_sequences}.csv
  data_in/ss_lewis_clark/{deployments,sequences}.csv
  geospatialdata/mammalranges/data_0.shp        (IUCN Red List mammal ranges)
  data_raw/usa_dashboard_2025.html               (2025 dashboard: IUCN-CONUS display polygons,
                                                  iNaturalist presence boundaries, palettes, ID tips)
  data_raw/mdd/                                  (MDD v2.5 species + synonym tables)
Outputs
  outputs/detections_range_check.csv   one row per project x deployment x taxon
  outputs/flag_review.csv              one row per project x subproject x taxon (flagged statuses)
  outputs/dashboard_payload.json       data embedded by build_dashboard.py

Status per (deployment, taxon), distance = km from the deployment to the nearest edge of the
species' IUCN range (presence 1-3, origin native/reintroduced/introduced/uncertain/assisted; vagrant
excluded) -- or, for the 12 dashboard groups, the nearer of IUCN and the iNaturalist presence boundary:
  in_range      <= 25 km
  near_edge     25-100 km
  out_of_range  > 100 km, or no range anywhere in the Americas, or an introduced species outside
                its documented US states
  introduced    introduced species with no IUCN US polygon, inside its documented US states
                (or no state list) -- plausible but verify
  genus_not_in_us   genus-level ID of a genus with no US species in MDD
  no_range_data     species occurs in US per MDD but no polygon available
  not_checked   family-level IDs; genus-level IDs of US genera
"""
import os, sys, json, re
import numpy as np, pandas as pd, geopandas as gpd, shapely, pyogrio
from shapely.geometry import box

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from mdd_resolve import Resolver, MDD_VERSION, MDD_DOI

DATA_IN = "/Users/rwkays/claude_code/data_in"
IUCN_SHP = "/Users/rwkays/claude_code/geospatialdata/mammalranges/data_0.shp"
OLD_HTML = os.path.join(PRJ, "data_raw", "usa_dashboard_2025.html")
OUT = os.path.join(PRJ, "outputs")
os.makedirs(OUT, exist_ok=True)

PROJECTS = {
    "ss26": dict(label="Snapshot USA 2026",
                 dep=f"{DATA_IN}/ss_usa26/ssusa_deployments.csv",
                 seq=f"{DATA_IN}/ss_usa26/ssusa_sequences.csv"),
    "lc": dict(label="Lewis & Clark Resurvey",
               dep=f"{DATA_IN}/ss_lewis_clark/deployments.csv",
               seq=f"{DATA_IN}/ss_lewis_clark/sequences.csv"),
}
FLEET34 = "/Users/rwkays/claude_code/geospatialdata/north_american_mammal_ranges/fleet34_isdm"
IN_KM, EDGE_KM = 25.0, 100.0
DOMESTIC = {"Homo sapiens", "Canis familiaris", "Felis catus", "Bos taurus", "Ovis aries",
            "Capra hircus", "Capra aegagrus hircus", "Equus caballus", "Equus asinus"}
# Wildlife Insights labels whose US animals belong to a different MDD v2.5 species after a split.
# The detection is range-checked under the MDD species; status 'taxonomy_label' when in range.
TAXON_RELABEL = {
    "Dasypus novemcinctus": ("Dasypus mexicanus", "MDD v2.5 restricts D. novemcinctus to South America; "
                             "armadillos in the US are D. mexicanus. Wildlife Insights label is outdated."),
    "Urva javanica": ("Urva auropunctata", "Mongooses introduced to Puerto Rico are Urva auropunctata in MDD v2.5 "
                      "(split from U. javanica, which is Southeast Asian). Wildlife Insights label is outdated."),
}
# Managed / ranched herds occur far outside the wild IUCN range -> 'introduced' (verify) when outside.
MANAGED = {"Bos bison": "Managed or ranched bison herds occur widely outside the IUCN wild range; verify."}
# MDD species split after the IUCN assessment: use the parent's (pre-split) IUCN polygon.
RANGE_PROXY = {"Glaucomys oregonensis": "Glaucomys sabrinus", "Martes caurina": "Martes americana",
               "Mustela richardsonii": "Mustela erminea", "Otospermophilus douglasii": "Otospermophilus beecheyi"}
# Introduced, naturalized species with no IUCN polygon in the US. None = no state restriction.
INTRODUCED = {"Axis axis": {"TX"}, "Boselaphus tragocamelus": {"TX"},
              "Cervus nippon": {"MD", "VA", "TX", "OK", "WI"},   # states listed in the 2025 dashboard notes
              "Sus scrofa": None, "Myocastor coypus": None, "Rattus rattus": None, "Rattus norvegicus": None,
              "Urva auropunctata": {"PR", "HI"}}
EXEMPT_GENERA = {n.split()[0] for n in list(DOMESTIC) + list(INTRODUCED) + list(MANAGED)} | {"Mus"}
SPECIAL_NOTES = {
    "Sciurus carolinensis or niger": "Two-species choice label; checked against the union of both ranges.",
}


def load_project(key):
    p = PROJECTS[key]
    dep = pd.read_csv(p["dep"], encoding="utf-8-sig", dtype=str, skipinitialspace=True)
    seq = pd.read_csv(p["seq"], encoding="utf-8-sig", dtype=str, skipinitialspace=True,
                      usecols=["project_id", "deployment_id", "sequence_id", "is_blank", "class", "order",
                               "family", "genus", "species", "common_name", "group_size"])
    for c in dep.columns:
        dep[c] = dep[c].str.strip().replace("", np.nan)
    for c in seq.columns:
        seq[c] = seq[c].str.strip().replace("", np.nan)
    n_dup = dep.duplicated(["project_id", "deployment_id"]).sum()
    dep = dep.drop_duplicates(["project_id", "deployment_id"], keep="first").copy()
    dep["latitude"] = dep.latitude.astype(float)
    dep["longitude"] = dep.longitude.astype(float)
    dep["array"] = dep.subproject_name.fillna(dep.placename).fillna(dep.deployment_id)
    dep["state"] = dep.array.str.extract(r"^([A-Z]{2})_")[0]
    seq = seq.merge(dep[["project_id", "deployment_id", "array"]], how="left")
    qc = dict(n_deployments=len(dep), n_dup_deployment_keys=int(n_dup),
              n_missing_subproject=int(dep.subproject_name.isna().sum()),
              n_sequences=len(seq), n_seq_no_deployment=int(seq.array.isna().sum()))
    return dep, seq, qc


def taxon_label(r):
    """Return (label, level) for one mammal sequence row."""
    g, s, f = r["genus"], r["species"], r["family"]
    if isinstance(s, str):
        return f"{g} {s}", "species"
    if isinstance(g, str):
        return f"{g} sp.", "genus"
    if isinstance(f, str):
        return f"{f} sp.", "family"
    return None, None


def main():
    R = Resolver()
    s = open(OLD_HTML).read()
    tag = '<script id="tab-data" type="application/json">'
    i = s.index(tag) + len(tag); j = s.index("</script>", i)
    TD = json.loads(s[i:j])
    TAB_GENERA = {g: k for k, v in TD.items() for g in v["taxnotes"]["genera"]}

    # ---------- detections ----------
    det_all, deps_all, qc_all = [], {}, {}
    for key in PROJECTS:
        dep, seq, qc = load_project(key)
        m = seq[(seq["class"] == "Mammalia") & (seq.is_blank != "1")].copy()
        lab = m.apply(taxon_label, axis=1, result_type="expand")
        m["verbatim"], m["level"] = lab[0], lab[1]
        m = m[m.verbatim.notna() & m.array.notna()]
        g = (m.groupby(["project_id", "deployment_id", "array", "verbatim", "level", "family", "genus"], dropna=False)
               .agg(n_seq=("sequence_id", "size"),
                    seq_ids=("sequence_id", lambda x: ";".join(list(x)[:10])))
               .reset_index())
        g["proj"] = key
        det_all.append(g); deps_all[key] = dep; qc_all[key] = qc
    det = pd.concat(det_all, ignore_index=True)

    # ---------- MDD resolution ----------
    sp_names = sorted(det.loc[det.level == "species", "verbatim"].unique())
    RES = R.table(sp_names).set_index("verbatim")
    det["mdd_sciName"] = det.verbatim.map(RES.mdd_sciName)
    det["mdd_id"] = det.verbatim.map(RES.mdd_id)
    det["match_type"] = det.verbatim.map(RES.match_type)
    det.loc[det.level == "species", "label"] = det.mdd_sciName.fillna(det.verbatim)
    det.loc[det.level != "species", "label"] = det.verbatim
    det["relabel_from"] = None
    for old, (new, why) in TAXON_RELABEL.items():
        m = det.label == old
        det.loc[m, "relabel_from"] = old
        det.loc[m, "label"] = new
        det.loc[m, "mdd_id"] = R.acc.loc[new, "id"]
        det.loc[m, "mdd_sciName"] = new

    # ---------- IUCN ranges (MDD-ID join) ----------
    att = pyogrio.read_dataframe(IUCN_SHP, read_geometry=False, columns=["SCI_NAME"])
    IT = R.table(sorted(att.SCI_NAME.dropna().unique()))
    iucn_name_to_id = dict(zip(IT.verbatim, IT.mdd_id))
    need = set(det.mdd_id.dropna())
    for a, b in RANGE_PROXY.items():
        need.add(R.acc.loc[b, "id"])
    for x in ("Sciurus carolinensis", "Sciurus niger", "Alces alces", "Dasypus mexicanus"):
        need.add(R.acc.loc[x, "id"])
    names = [n for n, m in iucn_name_to_id.items() if m in need]
    q = "SCI_NAME IN (" + ",".join("'" + n.replace("'", "''") + "'" for n in names) + ")"
    G = pyogrio.read_dataframe(IUCN_SHP, where=q, bbox=(-180, 0, -50, 85))
    G = G[G.PRESENCE.isin([1, 2, 3]) & G.ORIGIN.isin([1, 2, 3, 5, 6])].copy()
    G["mdd_id"] = G.SCI_NAME.map(iucn_name_to_id)
    G["geometry"] = shapely.make_valid(G.geometry.values)
    G = G.clip(box(-170, 5, -50, 75)); G = G[~G.geometry.is_empty]
    Gp = G.to_crs(5070)
    Gp["geometry"] = shapely.make_valid(Gp.geometry.values)
    def polys(g):
        if g.geom_type == "GeometryCollection":
            return shapely.unary_union([p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")])
        return g
    Gp["geometry"] = Gp.geometry.apply(polys)
    IUCN = {}
    for mid, g in Gp.groupby("mdd_id"):
        IUCN[mid] = shapely.union_all(g.geometry.values, grid_size=50).simplify(1000)
    # Alces alces display polygon for the Cervidae tab (2025 build had none)
    alces = G[G.mdd_id == R.acc.loc["Alces alces", "id"]]
    alces = alces.clip(box(-170, 24, -66, 72))
    alces_geo = shapely.union_all(alces.geometry.values, grid_size=0.001).simplify(0.02)

    # ---------- iNaturalist presence boundaries (from 2025 dashboard) ----------
    INAT = {}
    for k, v in TD.items():
        feats = [f for f in v["grid"]["features"]]
        if not feats:
            continue
        gg = gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(5070)
        for sci, g in gg.groupby("mdd_sciName"):
            mid = R.resolve(sci)["mdd_id"]
            if mid:
                INAT[mid] = shapely.make_valid(shapely.union_all(g.geometry.values))

    # fleet34 iNaturalist presence grids (100 km cells, EPSG:5070) as the second source for 34 species
    man = pd.read_csv(os.path.join(FLEET34, "fleet34_range_manifest.csv"))
    n_fleet = 0
    for _, mr in man.iterrows():
        fp = os.path.join(FLEET34, "grids_100km", f"{mr['species']}_presence_100km.geojson")
        mid = R.resolve(mr["binomial"])["mdd_id"]
        if not (mid and os.path.exists(fp)) or mid in INAT:
            continue
        gg = gpd.read_file(fp).to_crs(5070)
        gg = gg[(gg.n_records >= 2) | (gg.n_records < 0)]   # -1 = presence from the ISDM cache, count not stored
        if len(gg):
            INAT[mid] = shapely.union_all(gg.geometry.values); n_fleet += 1
    print("fleet34 presence grids added:", n_fleet)

    # ---------- distances ----------
    dep_xy = []
    for key, dep in deps_all.items():
        d = dep[["project_id", "deployment_id", "latitude", "longitude", "state", "array"]].copy(); d["proj"] = key
        dep_xy.append(d)
    dep_xy = pd.concat(dep_xy, ignore_index=True)
    pts = gpd.GeoSeries(gpd.points_from_xy(dep_xy.longitude, dep_xy.latitude), crs=4326).to_crs(5070)
    dep_xy["geom"] = pts.values
    det = det.merge(dep_xy, on=["proj", "project_id", "deployment_id", "array"], how="left")

    def range_ids(label):
        if label == "Sciurus carolinensis or niger":
            return [R.acc.loc["Sciurus carolinensis", "id"], R.acc.loc["Sciurus niger", "id"]], None
        r = R.resolve(label)
        mid = r["mdd_id"]
        if mid is None:
            return [], None
        if mid not in IUCN and label in RANGE_PROXY:
            return [R.acc.loc[RANGE_PROXY[label], "id"]], RANGE_PROXY[label]
        return [mid], None

    def dist_km(geoms, pt):
        geoms = [x for x in geoms if x is not None]
        if not geoms:
            return np.nan
        return min(shapely.distance(x, pt) for x in geoms) / 1000.0

    rows = []
    for idx, r in det.iterrows():
        label, level = r.label, r.level
        out = dict(status="not_checked", dist_iucn_km=np.nan, dist_inat_km=np.nan, dist_km=np.nan,
                   range_proxy=None, note=SPECIAL_NOTES.get(label))
        tab = TAB_GENERA.get(r.genus)
        if tab is None and r.family == "Cervidae":
            tab = "Cervidae"
        out["tab"] = tab
        if level == "species" or label == "Sciurus carolinensis or niger":
            if label in DOMESTIC or r.verbatim in DOMESTIC:
                out["status"] = "domestic"
            else:
                ids, proxy = range_ids(label)
                out["range_proxy"] = proxy
                di = dist_km([IUCN.get(m) for m in ids], r.geom)
                dn = dist_km([INAT.get(m) for m in ids], r.geom)
                out["dist_iucn_km"], out["dist_inat_km"] = di, dn
                d = np.nanmin([di, dn]) if not (np.isnan(di) and np.isnan(dn)) else np.nan
                out["dist_km"] = d
                if label in INTRODUCED and np.isnan(di):
                    states = INTRODUCED[label]
                    if states is None or r.state in states:
                        out["status"] = "introduced"
                    else:
                        out["status"] = "out_of_range"
                        out["note"] = f"Introduced species; documented US populations only in {', '.join(sorted(states))}; detected in {r.state}."
                elif not np.isnan(d):
                    out["status"] = "in_range" if d <= IN_KM else ("near_edge" if d <= EDGE_KM else "out_of_range")
                    if out["status"] == "out_of_range" and label in MANAGED:
                        out["status"] = "introduced"; out["note"] = MANAGED[label]
                else:
                    mid = ids[0] if ids else None
                    if mid is not None and not R.species_in_us(mid):
                        out["status"] = "out_of_range"
                        out["note"] = out["note"] or "No IUCN range in the Americas and MDD does not list the United States in this species' distribution."
                    else:
                        out["status"] = "no_range_data"
        elif level == "genus":
            gin = R.genus_in_us(r.genus)
            if gin is False and r.genus not in EXEMPT_GENERA:
                out["status"] = "genus_not_in_us"
                out["note"] = "No species of this genus occurs in the United States (MDD countryDistribution)."
        if isinstance(r.relabel_from, str):
            out["note"] = TAXON_RELABEL[r.relabel_from][1] + ((" " + out["note"]) if out["note"] else "")
            if out["status"] in ("in_range", "introduced"):
                out["status"] = "taxonomy_label"
        rows.append(out)
    det = pd.concat([det.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
    det["common"] = det.mdd_id.map(lambda m: R.common(m) if isinstance(m, str) else None)
    det = det.drop(columns=["geom"])
    det["mdd_version"] = MDD_VERSION
    det.to_csv(os.path.join(OUT, "detections_range_check.csv"), index=False)

    # ---------- subproject x taxon review table ----------
    sev = {"out_of_range": 0, "genus_not_in_us": 1, "near_edge": 2, "taxonomy_label": 3, "introduced": 4,
           "no_range_data": 5, "in_range": 6, "not_checked": 7, "domestic": 8}
    det["sev"] = det.status.map(sev)
    def agg(g):
        w = g.sort_values(["sev", "dist_km"], ascending=[True, False]).iloc[0]
        flagged = g[g.status.isin(["out_of_range", "near_edge", "genus_not_in_us"])]
        return pd.Series(dict(
            status=w.status, verbatim=";".join(sorted(g.verbatim.unique())), relabel_from=w.relabel_from,
            common=w.common, tab=w.tab, state=w.state, n_seq=int(g.n_seq.sum()),
            n_deployments=int(g.deployment_id.nunique()), n_dep_flagged=int(flagged.deployment_id.nunique()),
            max_dist_km=round(float(g.dist_km.max()), 1) if g.dist_km.notna().any() else None,
            min_dist_km=round(float(g.dist_km.min()), 1) if g.dist_km.notna().any() else None,
            range_proxy=w.range_proxy, note=w.note,
            deployments=";".join(sorted((flagged if len(flagged) else g).deployment_id.unique())[:8]),
            seq_ids=";".join(";".join((flagged if len(flagged) else g).seq_ids).split(";")[:10]),
            lat=float(g.latitude.mean()), lon=float(g.longitude.mean())))
    rev = det[det.status != "domestic"].groupby(["proj", "array", "label"]).apply(agg, include_groups=False).reset_index()
    rev.to_csv(os.path.join(OUT, "array_taxon_status.csv"), index=False)
    flag = rev[rev.status.isin(["out_of_range", "genus_not_in_us", "near_edge", "taxonomy_label", "introduced", "no_range_data"])]
    flag.sort_values(["proj", "status", "label"]).to_csv(os.path.join(OUT, "flag_review.csv"), index=False)

    payload = dict(projects={k: v["label"] for k, v in PROJECTS.items()}, qc=qc_all,
                   thresholds=dict(in_km=IN_KM, edge_km=EDGE_KM), mdd=f"{MDD_VERSION} (Zenodo {MDD_DOI})",
                   introduced=INTRODUCED and {k: (sorted(v) if v else None) for k, v in INTRODUCED.items()},
                   range_proxy=RANGE_PROXY, relabel={k: v[0] for k, v in TAXON_RELABEL.items()},
                   managed=list(MANAGED), n_inat_sources=len(INAT), n_fleet34=n_fleet,
                   alces_geojson=shapely.geometry.mapping(alces_geo),
                   arrays={}, review={})
    for key, dep in deps_all.items():
        a = dep.groupby("array").agg(lat=("latitude", "mean"), lon=("longitude", "mean"),
                                     n_deployments=("deployment_id", "nunique")).reset_index()
        payload["arrays"][key] = a.round(5).to_dict("records")
        payload["review"][key] = json.loads(rev[rev.proj == key].drop(columns=["proj"]).to_json(orient="records"))
    json.dump(payload, open(os.path.join(OUT, "dashboard_payload.json"), "w"))
    print(pd.crosstab(rev.status, rev.proj))
    print(json.dumps(qc_all, indent=1))


if __name__ == "__main__":
    main()
