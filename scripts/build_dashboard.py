"""Build docs/index.html: two-project (Snapshot USA 2026 / Lewis & Clark Resurvey) range-check dashboard.

Reuses the 2025 dashboard's CSS, IUCN display polygons, iNaturalist presence boundaries, palettes and
ID tips (data_raw/usa_dashboard_2025.html); camera-trap arrays and range-check statuses come from
outputs/dashboard_payload.json (scripts/build_range_check.py).
"""
import os, json, re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.abspath(os.path.join(HERE, ".."))
OLD_HTML = os.path.join(PRJ, "data_raw", "usa_dashboard_2025.html")
PAYLOAD = os.path.join(PRJ, "outputs", "dashboard_payload.json")
OUT_HTML = os.path.join(PRJ, "docs", "index.html")

EXTRA_COLORS = ["#e41a1c", "#984ea3", "#ff7f00", "#a65628", "#f781bf", "#377eb8", "#4daf4a",
                "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494"]
MUTED = ["#a39587", "#8c8c8c", "#b3a89c", "#7f7f7f", "#9c8f80", "#bdbdbd"]

EXTRA_META = {
    "Alces alces": ("Moose", "The largest deer: very tall at the shoulder with long legs, a drooping overhanging snout, "
                    "a dewlap ('bell') under the throat, and a dark brown to blackish body with paler legs. Bulls carry "
                    "broad palmate antlers. Unlikely to be confused with elk except in poor, distant images, where the "
                    "shoulder hump, long face and dark uniform colour are the best cues."),
    "Sciurus vulgaris": ("Eurasian red squirrel (not native to North America)",
                         "⚠ A Eurasian species with no wild North American population. Detections are almost certainly "
                         "misidentified American red squirrels (Tamiasciurus hudsonicus / T. douglasii) or red-phase "
                         "fox squirrels (Sciurus niger). Review the photos and re-label."),
    "Sciurus carolinensis or niger": ("Eastern gray or fox squirrel (two-species choice)",
                                      "Two-species label used when gray vs. fox squirrel could not be separated. "
                                      "Fox squirrels are larger with an orange/rusty belly and tail fringe; gray squirrels "
                                      "have a white belly and silvery tail fringe."),
    "Axis axis": ("Chital / axis deer (introduced)", "⚠ Native to South Asia. Established introduced herds in Texas "
                  "(and Hawaii). Bright rufous coat with persistent white spots in adults. Plausible in Texas ranch "
                  "country; elsewhere review as possible spotted white-tailed fawn."),
    "Capreolus sp.": ("Roe deer (genus not in North America)", "⚠ Eurasian genus; no North American population. "
                      "Likely a misidentified white-tailed or mule deer (often a doe or fawn)."),
    "Muntiacus sp.": ("Muntjac (genus not in North America)", "⚠ Asian genus; no wild North American population. "
                      "Likely a misidentified small deer or other mammal."),
}
STATUS_LABEL = {"out_of_range": "Outside known range", "genus_not_in_us": "Genus not in US",
                "near_edge": "Near range edge", "taxonomy_label": "Outdated WI name", "introduced": "Introduced/managed (verify)",
                "no_range_data": "No range data", "in_range": "In range", "not_checked": "Not checked"}


def main():
    s = open(OLD_HTML).read()
    tag = '<script id="tab-data" type="application/json">'
    i = s.index(tag) + len(tag); j = s.index("</script>", i)
    TD = json.loads(s[i:j])
    css = s[s.index("<style>"):s.index("</style>") + len("</style>")]
    icon_js_start = s.index("<script>", s.index("turf.min.js"))
    icon_js = s[icon_js_start:s.index("</script>", icon_js_start) + len("</script>")]
    P = json.load(open(PAYLOAD))
    TAB_KEYS = list(TD.keys())

    # Alces display polygon + palette/meta extensions
    TD["Cervidae"]["ranges"]["features"].append({"type": "Feature", "properties": {
        "mdd_sciName": "Alces alces", "genus": "Alces", "group": "Cervidae", "shapefile_names": "Alces alces",
        "presence_codes": "1-3", "origin_codes": "1", "seasonal_codes": "all", "n_source_features": 1},
        "geometry": P["alces_geojson"]})
    TD["Cervidae"]["taxnotes"].setdefault("taxonomy_decisions", []).append({
        "shapefile_name": "Alces alces", "mdd_name": "Alces alces", "match_type": "accepted_exact",
        "note": "Moose IUCN range polygon added in the 2026 build (it was missing from the 2025 dashboard), "
                "clipped to the US and Canada border region."})

    arrays_by_proj = {k: {a["array"]: a for a in v} for k, v in P["arrays"].items()}
    for k in TAB_KEYS:
        TD[k]["camtrap_by_project"] = {}
    used_extra = defaultdict(int)
    for proj, rows in P["review"].items():
        per = defaultdict(lambda: defaultdict(list))
        for r in rows:
            if r["tab"]:
                per[r["tab"]][r["array"]].append(r)
        for tab, arrs in per.items():
            pal, meta = TD[tab]["palette"], TD[tab]["meta"]
            out = []
            for arr, rs in arrs.items():
                for r in rs:
                    lab = r["label"]
                    if lab not in pal:
                        if lab.endswith(" sp."):
                            pal[lab] = MUTED[used_extra[(tab, "m")] % len(MUTED)]; used_extra[(tab, "m")] += 1
                        else:
                            pal[lab] = EXTRA_COLORS[used_extra[tab] % len(EXTRA_COLORS)]; used_extra[tab] += 1
                    if lab not in meta:
                        c, tips = EXTRA_META.get(lab, (r.get("common") or lab,
                                                       "Genus/family-level identification; photos need expert review."
                                                       if lab.endswith(" sp.") else "No ID notes for this taxon yet."))
                        meta[lab] = {"common": c, "id_tips": tips}
                rs = sorted(rs, key=lambda r: -r["n_seq"])
                a = arrays_by_proj[proj][arr]
                out.append(dict(subproject_name=arr, lat=a["lat"], lon=a["lon"], n_deployments=a["n_deployments"],
                                species_stripes=[dict(species=r["label"], count=r["n_seq"], status=r["status"],
                                                      max_dist_km=r["max_dist_km"], n_dep=r["n_deployments"],
                                                      n_dep_flagged=r["n_dep_flagged"], note=r["note"],
                                                      color=pal[r["label"]]) for r in rs]))
            TD[tab]["camtrap_by_project"][proj] = out
        # genus "sp." entries must be last in legend? keep insertion order
    for k in TAB_KEYS:
        TD[k].pop("camtrap", None)

    REVIEW = {"projects": P["projects"], "review": P["review"], "qc": P["qc"], "thresholds": P["thresholds"],
              "mdd": P["mdd"], "introduced": P["introduced"], "range_proxy": P["range_proxy"],
              "relabel": P["relabel"], "managed": P["managed"],
              "status_label": STATUS_LABEL}

    tabbuttons = "\n".join(f'  <button data-tab="{k}"{" class=\"active\"" if n == 0 else ""}>{k}</button>'
                           for n, k in enumerate(TAB_KEYS))
    projbuttons = "\n".join(f'    <button data-proj="{k}"{" class=\"active\"" if n == 0 else ""}>{v}</button>'
                            for n, (k, v) in enumerate(P["projects"].items()))
    html = (TEMPLATE.replace("%%CSS%%", css).replace("%%EXTRA_CSS%%", EXTRA_CSS)
            .replace("%%PROJBUTTONS%%", projbuttons).replace("%%TABBUTTONS%%", tabbuttons)
            .replace("%%ICONJS%%", icon_js)
            .replace("%%TABDATA%%", json.dumps(TD, separators=(",", ":")).replace("</", "<\\/"))
            .replace("%%REVIEWDATA%%", json.dumps(REVIEW, separators=(",", ":")).replace("</", "<\\/"))
            .replace("%%TABKEYS%%", json.dumps(TAB_KEYS))
            .replace("%%APPJS%%", APP_JS))
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    open(OUT_HTML, "w").write(html)
    print("wrote", OUT_HTML, round(len(html) / 1e6, 2), "MB")


EXTRA_CSS = """
<style>
  #projbar { display:flex; align-items:center; gap:10px; background:#081a2e; padding:6px 14px; flex-wrap:wrap; }
  #projbar .title { color:white; font-weight:700; font-size:15px; margin-right:auto; }
  #projbar .seg { display:flex; border:1px solid #3b5f8a; border-radius:6px; overflow:hidden; }
  #projbar .seg button { background:none; border:none; color:#cfe0f5; padding:7px 16px; font-size:13.5px; font-weight:600; cursor:pointer; }
  #projbar .seg button.active { background:#f0b429; color:#1c2530; }
  #projbar .stat { color:#cfe0f5; font-size:12px; }
  #projbar .stat b { color:#ffb3b3; }
  #tabbar .title { display:none; }
  #tabbar button[data-tab="__flags"] { color:#ffd0d0; }
  #tabbar button[data-tab="__flags"].active { background:#a11; color:white; }
  .tabpanel { height: calc(100vh - 88px); }
  .st { display:inline-block; padding:1px 6px; border-radius:9px; font-size:10.5px; font-weight:700; color:white; white-space:nowrap; }
  .st-out_of_range { background:#c00000; } .st-genus_not_in_us { background:#7b1fa2; }
  .st-near_edge { background:#e67e00; } .st-introduced { background:#b08d00; } .st-taxonomy_label { background:#1565c0; }
  .st-no_range_data { background:#607d8b; } .st-in_range { background:#2e7d32; } .st-not_checked { background:#9e9e9e; }
  .ct-tooltip table { border-collapse:collapse; font-size:11.5px; }
  .ct-tooltip td { padding:2px 5px; vertical-align:top; border-top:1px solid #eee; }
  .ct-note { font-size:10.5px; color:#555; max-width:260px; }
  #flagpanel { display:flex; height:100%; width:100%; }
  #flagmapwrap { flex: 1 1 45%; height:100%; }
  #flagmap { height:100%; width:100%; }
  #flagside { flex: 1 1 55%; height:100%; overflow:auto; padding:12px 16px 40px 16px; box-sizing:border-box; border-left:1px solid var(--border); }
  #flagside h1 { font-size:16px; margin:0 0 6px 0; }
  .ftools { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; font-size:12px; margin:8px 0; }
  .ftools input[type=text] { padding:5px 8px; border:1px solid var(--border); border-radius:5px; font-size:12.5px; min-width:200px; }
  .ftools button { background: var(--accent); color:white; border:none; border-radius:5px; padding:5px 10px; font-size:12px; cursor:pointer; }
  table.ftab { border-collapse:collapse; width:100%; font-size:11.8px; }
  table.ftab th { position:sticky; top:0; background:#eef2f6; text-align:left; padding:5px 6px; cursor:pointer; border-bottom:2px solid var(--border); white-space:nowrap; }
  table.ftab td { padding:4px 6px; border-bottom:1px solid #eceff2; vertical-align:top; }
  table.ftab tr:hover td { background:#fffbe6; cursor:pointer; }
  table.ftab td.ids { font-family: ui-monospace, Menlo, monospace; font-size:10.5px; color:#444; max-width:220px; word-break:break-all; }
  .summary-cards { display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 10px 0; }
  .summary-cards div { border:1px solid var(--border); border-radius:6px; padding:6px 10px; font-size:12px; }
  .summary-cards b { font-size:16px; display:block; }
  .methods { font-size:11.5px; color:var(--text-mid); line-height:1.5; background:#f7f9fb; border:1px solid var(--border); border-radius:8px; padding:8px 12px; margin-top:12px; }
  .layer-toggle.flagonly { margin-top:4px; }
</style>
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Snapshot USA Range Check -- 2026 &amp; Lewis and Clark Resurvey</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
%%CSS%%
%%EXTRA_CSS%%
</head>
<body>
<div id="projbar">
  <span class="title">Snapshot USA Range &amp; Taxonomy Check</span>
  <span class="stat" id="projstat"></span>
  <div class="seg">
%%PROJBUTTONS%%
  </div>
</div>
<div id="tabbar">
%%TABBUTTONS%%
  <button data-tab="__flags">&#9888; Range flags</button>
</div>
<div id="tabpanels"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/@turf/turf@6/turf.min.js"></script>
%%ICONJS%%
<script id="tab-data" type="application/json">%%TABDATA%%</script>
<script id="review-data" type="application/json">%%REVIEWDATA%%</script>
<script>
const TAB_KEYS = %%TABKEYS%%;
%%APPJS%%
</script>
</body>
</html>
"""

APP_JS = r"""
const TAB_DATA = JSON.parse(document.getElementById('tab-data').textContent);
const RV = JSON.parse(document.getElementById('review-data').textContent);
const PROJ_KEYS = Object.keys(RV.projects);
const USA_BOUNDS = [[24.0, -125.5], [49.5, -66.5]];
const FLAG_STATUSES = ['out_of_range','genus_not_in_us','near_edge'];
const SEV = {out_of_range:0, genus_not_in_us:1, near_edge:2, taxonomy_label:3, introduced:4, no_range_data:5, in_range:6, not_checked:7};
let currentProj = (location.hash.replace('#','').split('/')[0]) || PROJ_KEYS[0];
if (!PROJ_KEYS.includes(currentProj)) currentProj = PROJ_KEYS[0];
let currentTab = TAB_KEYS[0];
const mapsByTab = {};

function esc(x){ return (x==null?'':String(x)).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function commonName(sci, meta){ return (sci && meta[sci] && meta[sci].common) || sci || "Unknown"; }
function badge(st){ return `<span class="st st-${st}">${RV.status_label[st]||st}</span>`; }
function worstStatus(stripes){ let w='not_checked'; stripes.forEach(s=>{ if ((SEV[s.status]??9) < (SEV[w]??9)) w=s.status; }); return w; }

function iconFor(arr, palette){
  const colors = arr.species_stripes.map(s => s.color || palette[s.species] || '#999');
  const w = worstStatus(arr.species_stripes);
  const size = (w==='out_of_range'||w==='genus_not_in_us') ? 30 : 26;
  const ic = makeSplitSquareIcon(colors, size);
  let border = null;
  if (w==='out_of_range' || w==='genus_not_in_us') border = '#d00000';
  else if (w==='near_edge') border = '#ff8c00';
  if (border) {
    ic.options.html = ic.options.html.replace('stroke="#222222" stroke-width="1"', `stroke="${border}" stroke-width="4"`);
  }
  return ic;
}

function stripeRow(s, palette){
  const dist = (s.max_dist_km!=null && s.status!=='in_range') ? ` ${Math.round(s.max_dist_km)} km` : '';
  const nf = (s.n_dep_flagged>0) ? `<br><span class="ct-note">${s.n_dep_flagged}/${s.n_dep} detecting deployments flagged</span>` : '';
  const note = s.note ? `<br><span class="ct-note">${esc(s.note)}</span>` : '';
  return `<tr><td><span class="ct-swatch" style="background:${s.color || palette[s.species] || '#999'}"></span><i>${esc(s.species)}</i></td><td>${s.count}</td><td>${badge(s.status)}${dist}${nf}${note}</td></tr>`;
}

function buildTabHTML(tabKey){
  return `
    <div class="maparea"><div id="map_${tabKey}" class="mapdiv"></div></div>
    <div id="sidebar-wrap">
      <h1 class="dtitle">${tabKey} of the USA -- <span class="projname"></span></h1>
      <p class="sub">Click the map, or enter coordinates, to see which ${tabKey.toLowerCase()} species could occur there.
      Solid polygons: IUCN range maps. Hatched polygons: iNaturalist presence boundary (100 km cells with 2+ research-grade
      records). Squares: camera-trap arrays (subproject-level, mean deployment location), one stripe per taxon detected.
      <b style="color:#c00">Red-bordered squares</b> have at least one identification more than ${RV.thresholds.edge_km} km outside
      both range sources (or of a taxon not native to the US); <b style="color:#e67e00">orange</b> = ${RV.thresholds.in_km}-${RV.thresholds.edge_km} km outside.
      Distances are computed per deployment, not from the array's average location.</p>
      <details class="taxbox" id="taxbox_${tabKey}">
        <summary>Taxonomy Notes -- shapefile name vs. MDD-accepted name</summary>
        <div id="taxrows_${tabKey}"></div>
      </details>
      <h2 class="sect">Result</h2>
      <div class="lookup-box">
        <div class="lookup-row">
          <input id="latInput_${tabKey}" type="text" placeholder="Latitude (e.g. 39.5)">
          <input id="lonInput_${tabKey}" type="text" placeholder="Longitude (e.g. -98.4)">
        </div>
        <button id="lookupBtn_${tabKey}" style="width:100%;">Look up this location</button>
        <div class="hint">Or simply click a point on the map.</div>
      </div>
      <div id="coordEcho_${tabKey}" class="coord-echo"></div>
      <div id="results_${tabKey}"><div class="result-empty">Click the map or enter coordinates to see candidate species.</div></div>
      <h2 class="sect">Flagged identifications in this group</h2>
      <div id="tabflags_${tabKey}"></div>
      <h2 class="sect">Map layers</h2>
      <div class="layer-toggle" style="gap:10px;">
        <label for="rangeSourceSelect_${tabKey}" style="white-space:nowrap;">Range source:</label>
        <select id="rangeSourceSelect_${tabKey}" style="flex:1; padding:4px 6px; border:1px solid var(--border); border-radius:5px; font-size:12px;">
          <option value="iucn" selected>IUCN range polygons</option>
          <option value="inat">iNaturalist presence boundary</option>
          <option value="off">Off</option>
        </select>
      </div>
      <div class="layer-toggle"><input type="checkbox" id="toggleCamtrap_${tabKey}" checked> <label for="toggleCamtrap_${tabKey}">Camera-trap arrays</label></div>
      <div class="layer-toggle flagonly"><input type="checkbox" id="flagOnly_${tabKey}"> <label for="flagOnly_${tabKey}">Show only flagged arrays</label></div>
      <h2 class="sect">Species legend <span style="text-transform:none;font-weight:normal;">(click to isolate)</span></h2>
      <div id="legend_${tabKey}"></div>
      <p class="small-note" id="footnote_${tabKey}"></p>
    </div>`;
}

function renderTaxNotes(tabKey){
  const notes = TAB_DATA[tabKey].taxnotes || {};
  const decisions = notes.taxonomy_decisions || [];
  let html = decisions.length === 0 ? '<div class="taxrow">No taxonomy adjustments needed for the retained species in this group.</div>' :
    decisions.map(r => `<div class="taxrow"><div class="names">${r.shapefile_name} <span class="arrow">&rarr;</span> ${r.mdd_name}</div><div>${r.note}</div></div>`).join("");
  html += `<div class="taxrow"><div class="names">Taxonomic authority</div><div>${RV.mdd}</div></div>`;
  document.getElementById(`taxrows_${tabKey}`).innerHTML = html;
}

function renderTabFlags(tabKey){
  const data = TAB_DATA[tabKey];
  const arrs = (data.camtrap_by_project[currentProj] || []);
  const rows = [];
  arrs.forEach(a => a.species_stripes.forEach(s => { if (FLAG_STATUSES.includes(s.status) || s.status==='introduced' || s.status==='taxonomy_label') rows.push({a, s}); }));
  rows.sort((x,y)=> (SEV[x.s.status]-SEV[y.s.status]) || ((y.s.max_dist_km||0)-(x.s.max_dist_km||0)));
  const div = document.getElementById(`tabflags_${tabKey}`);
  if (!rows.length) { div.innerHTML = '<div class="result-empty">No flagged identifications for this group in this project.</div>'; return; }
  div.innerHTML = `<table class="ftab"><tr><th>Array</th><th>Taxon</th><th>Seq.</th><th>Status</th></tr>` +
    rows.map((r,i)=>`<tr data-i="${i}"><td>${esc(r.a.subproject_name)}</td><td><i>${esc(r.s.species)}</i></td><td>${r.s.count}</td><td>${badge(r.s.status)}${r.s.max_dist_km!=null?' '+Math.round(r.s.max_dist_km)+' km':''}</td></tr>`).join('') + '</table>';
  div.querySelectorAll('tr[data-i]').forEach(tr => tr.addEventListener('click', () => {
    const r = rows[+tr.dataset.i]; const m = mapsByTab[tabKey];
    m.map.setView([r.a.lat, r.a.lon], 7);
    const mk = m.markerIndex[r.a.subproject_name]; if (mk) mk.openPopup();
  }));
}

function buildCamtrapLayer(tabKey){
  const data = TAB_DATA[tabKey], palette = data.palette, m = mapsByTab[tabKey];
  if (m.camtrapLayerGroup) m.map.removeLayer(m.camtrapLayerGroup);
  const grp = L.layerGroup(); m.markerIndex = {};
  const flagOnly = document.getElementById(`flagOnly_${tabKey}`).checked;
  (data.camtrap_by_project[currentProj] || []).forEach(function(arr){
    if (arr.lat == null || !arr.species_stripes.length) return;
    const w = worstStatus(arr.species_stripes);
    if (flagOnly && !FLAG_STATUSES.includes(w)) return;
    const marker = L.marker([arr.lat, arr.lon], {icon: iconFor(arr, palette), zIndexOffset: FLAG_STATUSES.includes(w)?1000:0});
    marker.bindPopup(`<div class="ct-tooltip"><b>${esc(arr.subproject_name)}</b><br>${arr.n_deployments} deployments (avg. location)<br>` +
      `<table><tr><td><b>Taxon</b></td><td><b>Seq.</b></td><td><b>Range check</b></td></tr>${arr.species_stripes.map(s=>stripeRow(s, palette)).join('')}</table></div>`, {maxWidth: 420});
    grp.addLayer(marker); m.markerIndex[arr.subproject_name] = marker;
  });
  m.camtrapLayerGroup = grp;
  if (document.getElementById(`toggleCamtrap_${tabKey}`).checked) grp.addTo(m.map);
  renderTabFlags(tabKey);
}

function initTabMap(tabKey){
  const data = TAB_DATA[tabKey], palette = data.palette, meta = data.meta;
  const map = L.map(`map_${tabKey}`, { preferCanvas: true });
  map.fitBounds(USA_BOUNDS);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors', maxZoom: 18 }).addTo(map);
  const rangeLayer = L.geoJSON(data.ranges, { style: f => { const c = palette[f.properties.mdd_sciName] || '#555';
      return { color:c, weight:1.2, fillColor:c, fillOpacity:0.28, opacity:0.85 }; } }).addTo(map);
  const gridLayer = L.geoJSON(data.grid, { style: f => { const c = palette[f.properties.mdd_sciName] || '#555';
      return { color:c, weight:2, fillColor:c, fillOpacity:0.12, opacity:0.9, dashArray:'6,3' }; } });
  mapsByTab[tabKey] = { map, rangeLayer, gridLayer, camtrapLayerGroup: null, markerIndex: {} };
  buildCamtrapLayer(tabKey);

  const sel = document.getElementById(`rangeSourceSelect_${tabKey}`);
  sel.addEventListener('change', function(e){
    map.removeLayer(rangeLayer); map.removeLayer(gridLayer);
    if (e.target.value === 'iucn') map.addLayer(rangeLayer); else if (e.target.value === 'inat') map.addLayer(gridLayer);
  });
  document.getElementById(`toggleCamtrap_${tabKey}`).addEventListener('change', e => { const g = mapsByTab[tabKey].camtrapLayerGroup; e.target.checked ? map.addLayer(g) : map.removeLayer(g); });
  document.getElementById(`flagOnly_${tabKey}`).addEventListener('change', () => buildCamtrapLayer(tabKey));

  const legendDiv = document.getElementById(`legend_${tabKey}`);
  let isolated = null;
  function renderLegend(){
    legendDiv.innerHTML = '';
    Object.keys(palette).forEach(function(sci){
      const row = document.createElement('div');
      row.className = 'legend-item' + (isolated && isolated !== sci ? ' off' : '');
      row.innerHTML = `<span class="legend-swatch" style="background:${palette[sci]}"></span><span>${sci} — ${commonName(sci, meta)}</span>`;
      row.addEventListener('click', function(){ isolated = (isolated === sci) ? null : sci; applyIsolation(); renderLegend(); });
      legendDiv.appendChild(row);
    });
  }
  function applyIsolation(){
    rangeLayer.eachLayer(l => { const show = !isolated || isolated === l.feature.properties.mdd_sciName; l.setStyle({ opacity: show?0.85:0.05, fillOpacity: show?0.28:0.02 }); });
    gridLayer.eachLayer(l => { const show = !isolated || isolated === l.feature.properties.mdd_sciName; l.setStyle({ opacity: show?0.9:0.05, fillOpacity: show?0.12:0.02 }); });
  }
  renderLegend();

  const resultsDiv = document.getElementById(`results_${tabKey}`), coordEcho = document.getElementById(`coordEcho_${tabKey}`);
  let queryMarker = null;
  const srcName = v => v === 'iucn' ? 'IUCN range' : 'iNaturalist presence boundary';
  function hits(lat, lon){
    const v = sel.value; if (v === 'off') return null;
    const pt = turf.point([lon, lat]); const fs = v === 'iucn' ? data.ranges.features : (data.grid.features || []);
    const out = []; fs.forEach(f => { try { if (turf.booleanPointInPolygon(pt, f)) out.push(f.properties.mdd_sciName); } catch(e){} });
    return out;
  }
  function runLookup(lat, lon){
    coordEcho.textContent = `Queried location: ${lat.toFixed(4)}, ${lon.toFixed(4)}`;
    if (queryMarker) map.removeLayer(queryMarker);
    queryMarker = L.marker([lat, lon]).addTo(map);
    const matches = hits(lat, lon);
    if (matches === null) { resultsDiv.innerHTML = '<div class="result-empty">No range source selected. Choose IUCN or iNaturalist under Map layers.</div>'; return; }
    resultsDiv.innerHTML = `<div class="hint" style="margin-bottom:6px;">Based on: ${srcName(sel.value)}</div>`;
    if (!matches.length) { resultsDiv.innerHTML += `<div class="result-empty">No ${srcName(sel.value)} data covers this point.</div>`; return; }
    if (matches.length > 1) resultsDiv.innerHTML += `<div class="overlap-banner">⚠️ <b>${matches.length} species</b> may co-occur here: ${matches.map(s=>commonName(s, meta)).join(', ')}.</div>`;
    matches.forEach(sci => { const m = meta[sci] || {};
      resultsDiv.innerHTML += `<div class="sp-card" style="border-left-color:${palette[sci]||'#999'}"><h3>${m.common||sci}</h3><div class="sci">${sci}</div><div class="tips"><b>ID tips:</b> ${m.id_tips||'No notes available.'}</div></div>`; });
  }
  const hoverTooltip = L.tooltip({sticky:true, opacity:0.95});
  map.on('mousemove', function(e){
    const h = hits(e.latlng.lat, e.latlng.lng);
    if (!h || !h.length) { map.closeTooltip(hoverTooltip); return; }
    const label = h.map(s => commonName(s, meta)).join(', ');
    hoverTooltip.setContent(`<b>${h.length>1 ? h.length+' species' : label}</b>` + (h.length>1?`<br>${label}`:'') + `<br><span style="font-size:10px;color:#888;">${srcName(sel.value)}</span>`);
    hoverTooltip.setLatLng(e.latlng); if (!map.hasLayer(hoverTooltip)) hoverTooltip.addTo(map);
  });
  map.on('mouseout', () => map.closeTooltip(hoverTooltip));
  map.on('click', e => runLookup(e.latlng.lat, e.latlng.lng));
  document.getElementById(`lookupBtn_${tabKey}`).addEventListener('click', function(){
    const lat = parseFloat(document.getElementById(`latInput_${tabKey}`).value), lon = parseFloat(document.getElementById(`lonInput_${tabKey}`).value);
    if (isNaN(lat) || isNaN(lon)) { resultsDiv.innerHTML = '<div class="result-empty">Please enter valid numeric latitude and longitude.</div>'; return; }
    map.setView([lat, lon], 6); runLookup(lat, lon);
  });
  document.getElementById(`footnote_${tabKey}`).innerHTML =
    'Range maps: IUCN Red List species distribution polygons (display layer clipped to the US). iNaturalist presence boundary: ' +
    'dissolved 100 km grid cells (research-grade records, 2+ observations per cell). Range-check distances use the full IUCN polygons ' +
    '(extant/probably/possibly extant; native, reintroduced, introduced) and, for this group, the iNaturalist boundary; the nearer of the two is used. ' +
    'Taxonomy reconciled to ' + RV.mdd + '. Identification notes are compiled from standard field-guide knowledge -- confirm against a current field guide.';
}

// ---------------- Range flags tab ----------------
let flagMap = null, flagLayer = null, flagSort = {key:'status', dir:1};
const FLAG_COLS = [['status','Status'],['label','Taxon'],['array','Array (subproject)'],['n_seq','Seq.'],['n_deployments','Dep.'],['n_dep_flagged','Dep. flagged'],['max_dist_km','Max km'],['note','Note'],['deployments','Deployments'],['seq_ids','Example sequence IDs']];
const STATUS_ORDER = ['out_of_range','genus_not_in_us','near_edge','taxonomy_label','introduced','no_range_data'];
const statusOn = {out_of_range:true, genus_not_in_us:true, near_edge:true, taxonomy_label:true, introduced:true, no_range_data:false};
const STCOL = {out_of_range:'#c00000', genus_not_in_us:'#7b1fa2', near_edge:'#e67e00', taxonomy_label:'#1565c0', introduced:'#b08d00', no_range_data:'#607d8b'};

function buildFlagsHTML(){
  return `<div id="flagpanel"><div id="flagmapwrap"><div id="flagmap"></div></div>
    <div id="flagside"><h1>Range flags -- <span class="projname"></span></h1>
    <p class="sub">Every wild-mammal identification (all taxa, not only the 12 tab groups) checked against its range at the deployment location.
    One row per array &times; taxon; status is the worst deployment in that array. Click a row to zoom the map.</p>
    <div class="summary-cards" id="flagcards"></div>
    <div class="ftools" id="flagtools"></div>
    <div id="flagtable"></div>
    <div class="methods" id="flagmethods"></div></div></div>`;
}
function reviewRows(){ return (RV.review[currentProj] || []).filter(r => STATUS_ORDER.includes(r.status)); }
function renderFlags(){
  const all = reviewRows();
  const cnt = {}; all.forEach(r => cnt[r.status] = (cnt[r.status]||0)+1);
  document.getElementById('flagcards').innerHTML = STATUS_ORDER.map(s => `<div style="border-left:4px solid ${STCOL[s]}"><b>${cnt[s]||0}</b>${RV.status_label[s]}</div>`).join('') +
    `<div><b>${new Set(all.filter(r=>FLAG_STATUSES.includes(r.status)).map(r=>r.label)).size}</b>taxa flagged</div>`;
  const tools = document.getElementById('flagtools');
  if (!tools.dataset.built) {
    tools.innerHTML = STATUS_ORDER.map(s => `<label><input type="checkbox" data-st="${s}" ${statusOn[s]?'checked':''}> ${badge(s)}</label>`).join('') +
      `<input type="text" id="flagsearch" placeholder="Filter taxon / array / state..."> <button id="flagcsv">Download CSV</button>`;
    tools.querySelectorAll('input[data-st]').forEach(cb => cb.addEventListener('change', e => { statusOn[e.target.dataset.st] = e.target.checked; renderFlags(); }));
    document.getElementById('flagsearch').addEventListener('input', renderFlags);
    document.getElementById('flagcsv').addEventListener('click', downloadCSV);
    tools.dataset.built = '1';
  }
  const q = document.getElementById('flagsearch').value.toLowerCase();
  let rows = all.filter(r => statusOn[r.status] && (!q || (r.label+' '+r.array+' '+(r.verbatim||'')+' '+(r.common||'')).toLowerCase().includes(q)));
  const k = flagSort.key, d = flagSort.dir;
  rows.sort((a,b) => { let x=a[k], y=b[k]; if (k==='status'){ x=SEV[x]; y=SEV[y]; }
    if (x==null) return 1; if (y==null) return -1; return (x>y?1:x<y?-1:0)*d || ((b.max_dist_km||0)-(a.max_dist_km||0)); });
  const tbl = document.getElementById('flagtable');
  tbl.innerHTML = `<table class="ftab"><tr>${FLAG_COLS.map(([c,n])=>`<th data-k="${c}">${n}${flagSort.key===c?(d>0?' ▲':' ▼'):''}</th>`).join('')}</tr>` +
    rows.map((r,i) => `<tr data-i="${i}"><td>${badge(r.status)}</td><td><i>${esc(r.label)}</i>${r.common?'<br><span class="ct-note">'+esc(r.common)+'</span>':''}${r.verbatim!==r.label?'<br><span class="ct-note">WI label: '+esc(r.verbatim)+'</span>':''}</td><td>${esc(r.array)}</td><td>${r.n_seq}</td><td>${r.n_deployments}</td><td>${r.n_dep_flagged}</td><td>${r.max_dist_km!=null?Math.round(r.max_dist_km):''}</td><td class="ct-note">${esc(r.note||'')}${r.range_proxy?' Range proxy: '+esc(r.range_proxy)+' (pre-split IUCN polygon).':''}</td><td class="ids">${esc((r.deployments||'').split(';').join('; '))}</td><td class="ids">${esc((r.seq_ids||'').split(';').join('; '))}</td></tr>`).join('') + '</table>';
  tbl.querySelectorAll('th[data-k]').forEach(th => th.addEventListener('click', () => { const kk = th.dataset.k; flagSort = {key:kk, dir: flagSort.key===kk ? -flagSort.dir : 1}; renderFlags(); }));
  tbl.querySelectorAll('tr[data-i]').forEach(tr => tr.addEventListener('click', () => { const r = rows[+tr.dataset.i]; flagMap.setView([r.lat, r.lon], 8);
    flagLayer.eachLayer(l => { if (l.options.rowref === r) l.openPopup(); }); }));
  if (flagLayer) flagMap.removeLayer(flagLayer);
  flagLayer = L.layerGroup();
  rows.slice().sort((a,b)=>SEV[b.status]-SEV[a.status]).forEach(r => {
    const mk = L.circleMarker([r.lat, r.lon], {radius: FLAG_STATUSES.includes(r.status)?7:5, color:'#222', weight:1, fillColor: STCOL[r.status], fillOpacity:0.85, rowref: r});
    mk.bindPopup(`<b>${esc(r.array)}</b><br><i>${esc(r.label)}</i> -- ${r.n_seq} seq.<br>${badge(r.status)} ${r.max_dist_km!=null?Math.round(r.max_dist_km)+' km from range':''}<br><span class="ct-note">${esc(r.note||'')}</span>`);
    flagLayer.addLayer(mk);
  });
  flagLayer.addTo(flagMap);
  const qc = RV.qc[currentProj];
  document.getElementById('flagmethods').innerHTML =
    `<b>Method.</b> Names resolved to ${RV.mdd} species IDs (exact or full-binomial synonym match; IUCN polygons joined on MDD ID, not name strings). ` +
    `Distance = km from each deployment to the nearest edge of the species' IUCN range (presence extant/probably/possibly; origin native, reintroduced, introduced, uncertain, assisted; vagrant excluded), ` +
    `or the nearer of IUCN and an iNaturalist presence boundary where one exists (the 12 tab groups plus the fleet-34 ISDM presence grids for common mid-size mammals). In range &le; ${RV.thresholds.in_km} km; near edge ${RV.thresholds.in_km}-${RV.thresholds.edge_km} km; outside &gt; ${RV.thresholds.edge_km} km. ` +
    `Species with no range anywhere in the Americas and no US record in MDD are "outside". Introduced species without an IUCN US polygon are "introduced (verify)" inside their documented states (` +
    Object.entries(RV.introduced).map(([k,v]) => `<i>${k}</i>: ${v?v.join('/'):'any'}`).join('; ') + `) and "outside" elsewhere. ` +
    `Recent MDD splits without their own IUCN polygon use the parent's pre-split range: ` + Object.entries(RV.range_proxy).map(([k,v])=>`<i>${k}</i> &rarr; <i>${v}</i>`).join('; ') + `. ` +
    `Outdated Wildlife Insights names after MDD splits are relabeled and checked under the MDD species (` + Object.entries(RV.relabel).map(([k,v])=>`<i>${k}</i> &rarr; <i>${v}</i>`).join('; ') + `). ` +
    `Managed herds (` + RV.managed.map(x=>`<i>${x}</i>`).join(', ') + `) outside the wild range are "introduced/managed (verify)". ` +
    `Genus-level IDs are flagged only when no species of that genus occurs in the US (genera of domestic/introduced species exempt); family-level IDs are not checked. Domestic animals and humans excluded.<br>` +
    `<b>Data QC (${RV.projects[currentProj]}).</b> ${qc.n_deployments} deployments (${qc.n_dup_deployment_keys} duplicate deployment IDs dropped, keeping the first location; ` +
    `${qc.n_missing_subproject} with no subproject name, grouped by placename); ${qc.n_sequences.toLocaleString()} sequences, ${qc.n_seq_no_deployment} with no matching deployment (excluded).`;
}
function downloadCSV(){
  const rows = reviewRows(); const cols = ['status','label','verbatim','common','array','state','n_seq','n_deployments','n_dep_flagged','min_dist_km','max_dist_km','range_proxy','note','deployments','seq_ids','lat','lon'];
  const csv = [cols.join(',')].concat(rows.map(r => cols.map(c => { const v = r[c]==null?'':String(r[c]); return /[",\n]/.test(v) ? '"'+v.replace(/"/g,'""')+'"' : v; }).join(','))).join('\n');
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], {type:'text/csv'}));
  a.download = `range_flags_${currentProj}.csv`; a.click();
}
function initFlags(){
  flagMap = L.map('flagmap', {preferCanvas:true}); flagMap.fitBounds(USA_BOUNDS);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'&copy; OpenStreetMap contributors', maxZoom:18}).addTo(flagMap);
  renderFlags();
}

// ---------------- wiring ----------------
const panels = document.getElementById('tabpanels');
TAB_KEYS.forEach((k, i) => { const p = document.createElement('div'); p.className = 'tabpanel' + (i===0?' active':''); p.id = `panel_${k}`; p.innerHTML = buildTabHTML(k); panels.appendChild(p); renderTaxNotes(k); });
{ const p = document.createElement('div'); p.className = 'tabpanel'; p.id = 'panel___flags'; p.innerHTML = buildFlagsHTML(); panels.appendChild(p); }
const ALL_TABS = TAB_KEYS.concat(['__flags']);

function updateProjLabels(){
  document.querySelectorAll('.projname').forEach(e => e.textContent = RV.projects[currentProj]);
  document.querySelectorAll('#projbar .seg button').forEach(b => b.classList.toggle('active', b.dataset.proj === currentProj));
  const rows = RV.review[currentProj] || []; const n = rows.filter(r => r.status==='out_of_range' || r.status==='genus_not_in_us').length;
  const taxa = new Set(rows.filter(r => r.status==='out_of_range' || r.status==='genus_not_in_us').map(r=>r.label)).size;
  document.getElementById('projstat').innerHTML = `<b>${n}</b> array&times;taxon records outside range (${taxa} taxa)`;
}
function activateTab(tabKey){
  currentTab = tabKey;
  ALL_TABS.forEach(k => { document.getElementById(`panel_${k}`).classList.toggle('active', k===tabKey);
    document.querySelector(`#tabbar button[data-tab="${k}"]`).classList.toggle('active', k===tabKey); });
  if (tabKey === '__flags') { if (!flagMap) initFlags(); setTimeout(()=>flagMap.invalidateSize(), 50); }
  else { if (!mapsByTab[tabKey]) initTabMap(tabKey); setTimeout(()=>mapsByTab[tabKey].map.invalidateSize(), 50); }
  history.replaceState(null, '', `#${currentProj}/${tabKey}`);
}
function setProject(p){
  currentProj = p; updateProjLabels();
  Object.keys(mapsByTab).forEach(k => buildCamtrapLayer(k));
  if (flagMap) renderFlags();
  history.replaceState(null, '', `#${currentProj}/${currentTab}`);
}
document.querySelectorAll('#tabbar button[data-tab]').forEach(b => b.addEventListener('click', () => activateTab(b.dataset.tab)));
document.querySelectorAll('#projbar .seg button').forEach(b => b.addEventListener('click', () => setProject(b.dataset.proj)));
updateProjLabels();
const hashTab = location.hash.split('/')[1];
activateTab(ALL_TABS.includes(hashTab) ? hashTab : TAB_KEYS[0]);
"""

if __name__ == "__main__":
    main()
