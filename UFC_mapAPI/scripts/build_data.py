#!/usr/bin/env python3
"""
UFC Gyms Map — Data Pipeline
============================
Scrapes UFC top-10 rankings per weight class, finds each fighter's training
gym via Wikipedia, geocodes with Nominatim (OpenStreetMap, free — no API key),
then generates a self-contained map.html you can open directly in a browser.

Usage:
    python scripts/build_data.py
    python scripts/build_data.py --top 15

Outputs (relative to UFC_mapAPI/):
    data/fighter_gyms.csv      — fighter/gym/coordinates table
    data/fighter_gyms.geojson  — GeoJSON for the map
    map.html                   — self-contained interactive map

Requirements:
    pip install requests beautifulsoup4 pandas
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ── paths (resolved relative to this script file) ─────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.join(SCRIPT_DIR, '..')          # UFC_mapAPI/
DATA_DIR   = os.path.join(BASE_DIR, 'data')
MAP_PATH   = os.path.join(BASE_DIR, 'map.html')

# ── constants ──────────────────────────────────────────────────────────────────
UFC_URL       = 'https://www.ufc.com/rankings'
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
NOMINATIM_UA  = 'ufc-gyms-map/1.0 (github.com/Brettzim/ufc_gyms_map)'
DEFAULT_TOP_N = 10

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; ufc-gyms-map/1.0)'}


# ══════════════════════════════════════════════════════════════════════════════
# Step 1 — Scrape UFC rankings
# ══════════════════════════════════════════════════════════════════════════════

def scrape_rankings(top_n: int = DEFAULT_TOP_N) -> dict:
    """Return {weight_class: {rank_str: fighter_name}} for top_n fighters + champion."""
    print(f"[1/4] Scraping UFC rankings (top {top_n} per weight class) ...")
    resp = requests.get(UFC_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    rankings = {}
    for group in soup.select('.view-grouping'):
        weight_class = group.select_one('.view-grouping-header').text.strip()

        # Skip pound-for-pound lists — no gyms to map there
        if 'pound-for-pound' in weight_class.lower():
            continue

        wc: dict[str, str] = {}

        champ_el = group.select_one('.rankings--athlete--champion .info h5 a')
        if champ_el:
            wc['Champion'] = champ_el.text.strip()

        for row in group.select('tbody tr'):
            rank_el = row.select_one('.views-field-weight-class-rank')
            name_el = row.select_one('.views-field-title a')
            if not rank_el or not name_el:
                continue
            rank = rank_el.text.strip()
            try:
                if int(rank) <= top_n:
                    wc[rank] = name_el.text.strip()
            except ValueError:
                pass  # non-numeric rank string — skip

        if wc:
            rankings[weight_class] = wc

    total_fighters = sum(len(v) for v in rankings.values())
    print(f"     {len(rankings)} weight classes, {total_fighters} fighters")
    return rankings


# ══════════════════════════════════════════════════════════════════════════════
# Step 2 — Wikipedia gym lookup
# ══════════════════════════════════════════════════════════════════════════════

def _parse_gym_text(raw: str) -> str | None:
    """Clean raw Wikipedia infobox 'Team' cell text into a single gym name."""
    # Strip citation markers like [1], [2]
    text = re.sub(r'\[\d+\]', '', raw)
    parts = [p.strip() for p in text.split('\n') if p.strip()]
    if not parts:
        return None

    # Prefer the line that contains 'present' (most recent team)
    for part in reversed(parts):
        if 'present' in part.lower():
            cleaned = re.sub(r'\(.*?present.*?\)', '', part, flags=re.IGNORECASE)
            return cleaned.strip() or None

    # Fallback: first listed gym (primary affiliation), strip trailing year ranges
    first = re.sub(r'\(\d{4}[–\-]\d{4}\)', '', parts[0]).strip()
    return first or None


def get_gym(fighter_name: str) -> str | None:
    """Look up fighter's training gym from their Wikipedia infobox."""
    url = f"https://en.wikipedia.org/wiki/{fighter_name.replace(' ', '_')}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        infobox = soup.find('table', {'class': 'infobox'})
        if not infobox:
            return None
        for row in infobox.find_all('tr'):
            th = row.find('th')
            td = row.find('td')
            if th and td and 'team' in th.text.lower():
                # Use separator='\n' so each <li>/<br> element gets its own line
                return _parse_gym_text(td.get_text(separator='\n'))
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Step 3 — Nominatim geocoding (OpenStreetMap, free, no API key)
# ══════════════════════════════════════════════════════════════════════════════

def geocode(gym_name: str) -> tuple[float | None, float | None]:
    """Return (lat, lon) for a gym name using Nominatim, or (None, None)."""
    params  = {'q': gym_name, 'format': 'json', 'limit': 1}
    headers = {'User-Agent': NOMINATIM_UA}
    try:
        data = requests.get(
            NOMINATIM_URL, params=params, headers=headers, timeout=10
        ).json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        pass
    return None, None


# ══════════════════════════════════════════════════════════════════════════════
# Step 4a — Build nationality heatmap points
# ══════════════════════════════════════════════════════════════════════════════

# Maps Grok nationality strings → names used in the world GeoJSON
# (holtzy/D3-graph-gallery world.geojson uses standard English country names)
NATIONALITY_NORM: dict[str, str] = {
    # USA variants
    'United States': 'USA',
    'United States of America': 'USA',
    'US': 'USA',
    'American': 'USA',
    'Puerto Rico': 'USA',
    # UK — GeoJSON uses "England" for the whole UK polygon
    'United Kingdom': 'England',
    'UK': 'England',
    'Scotland': 'England',
    'Wales': 'England',
    'Northern Ireland': 'England',
    # Other name differences
    'Bosnia': 'Bosnia and Herzegovina',
    'Serbia': 'Republic of Serbia',
    'Trinidad': 'Trinidad and Tobago',
    'Czechia': 'Czech Republic',
    # pass-through (already match GeoJSON): Russia, Brazil, Mexico, Canada,
    # China, Australia, Poland, France, Japan, Georgia, Argentina, New Zealand,
    # Ecuador, Nigeria, Kyrgyzstan, Morocco, Iraq, Kazakhstan, Portugal,
    # Myanmar, Armenia, Ireland, South Africa, Netherlands, Czech Republic,
    # Uzbekistan, Switzerland, Dominican Republic, Moldova, Croatia, Kosovo
}


def build_country_counts(df: 'pd.DataFrame') -> dict[str, int]:
    """Return {geo_country_name: fighter_count} from the Nationality column."""
    if 'Nationality' not in df.columns:
        return {}
    counts: dict[str, int] = {}
    for nat in df['Nationality'].dropna():
        nat = str(nat).strip()
        geo = NATIONALITY_NORM.get(nat, nat)   # normalise; fall back to raw value
        counts[geo] = counts.get(geo, 0) + 1
    return counts


# ══════════════════════════════════════════════════════════════════════════════
# Step 4b — Build GeoJSON
# ══════════════════════════════════════════════════════════════════════════════

def build_geojson(df: 'pd.DataFrame') -> dict:
    """Group fighters by gym location and return a GeoJSON FeatureCollection.

    Expects columns: Division, Rank, Fighter, Gym, City, Country, Latitude, Longitude
    """
    gyms: dict[tuple, list] = defaultdict(list)
    for _, row in df.iterrows():
        lat = float(row['Latitude']) if pd.notna(row['Latitude']) else None
        lon = float(row['Longitude']) if pd.notna(row['Longitude']) else None
        if lat is not None and lon is not None:
            key = (str(row['Gym']), str(row['City']), str(row['Country']), lat, lon)
            gyms[key].append(row)

    # Sort order for ranks: C first, IC second, then numeric
    def rank_sort_key(rank):
        r = str(rank)
        if r == 'C':  return (0, 0)
        if r == 'IC': return (0, 1)
        try:          return (1, int(r))
        except ValueError: return (2, 0)

    features = []
    for (gym, city, country, lat, lon), members in gyms.items():
        sorted_members = sorted(members, key=lambda r: (r['Division'], rank_sort_key(r['Rank'])))
        lines = '<br>'.join(
            f"{r['Fighter']} &mdash; {r['Division']} &bull; {r['Rank']}"
            for r in sorted_members
        )
        features.append({
            'type': 'Feature',
            'properties': {
                'gym':    gym,
                'popup':  (f'<strong>{gym}</strong>'
                           f'<br><span style="opacity:0.6;font-size:11px">{city}, {country}</span>'
                           f'<br><br>{lines}'),
                'count':  len(members),
            },
            'geometry': {
                'type':        'Point',
                'coordinates': [lon, lat],
            },
        })

    return {'type': 'FeatureCollection', 'features': features}


# ══════════════════════════════════════════════════════════════════════════════
# Step 5 — Generate self-contained map.html
# ══════════════════════════════════════════════════════════════════════════════

MAP_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>UFC Gyms Map</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #111; }}
  #map {{ position: absolute; top: 0; bottom: 0; width: 100%; }}

  .leaflet-popup-content-wrapper {{
    background: #1a1a1a;
    color: #f0f0f0;
    border-radius: 8px;
    box-shadow: 0 2px 16px rgba(0,0,0,.7);
  }}
  .leaflet-popup-content {{
    font-size: 13px;
    line-height: 1.75;
    margin: 12px 16px;
    min-width: 180px;
    max-width: 280px;
  }}
  .leaflet-popup-tip {{ background: #1a1a1a; }}
  .leaflet-popup-close-button {{ color: #aaa !important; }}

  #legend {{
    position: absolute;
    bottom: 36px;
    left: 12px;
    z-index: 1000;
    background: rgba(20,20,20,0.9);
    color: #ddd;
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 12px;
    line-height: 2.2;
    box-shadow: 0 2px 10px rgba(0,0,0,.5);
    min-width: 190px;
  }}
  #legend strong {{ color: #fff; display: block; margin-bottom: 2px; }}
  #legend hr {{ border: none; border-top: 1px solid #333; margin: 6px 0; }}
  .dot {{
    display: inline-block; width: 11px; height: 11px;
    border-radius: 50%; margin-right: 7px; vertical-align: middle;
    border: 1.5px solid rgba(255,255,255,0.35);
  }}
  .heat-bar {{
    display: inline-block;
    width: 80px; height: 8px;
    margin-right: 7px; vertical-align: middle;
    border-radius: 4px;
    background: linear-gradient(to right, #300, #a00, #ff2200);
    opacity: 0.85;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div id="legend">
  <strong>Fighter nationality</strong>
  <div><span class="heat-bar"></span>low &rarr; high</div>
  <hr>
  <strong>Training gym (ranked fighters)</strong>
  <div><span class="dot" style="background:#4a9eda"></span>1 fighter</div>
  <div><span class="dot" style="background:#ff6b35"></span>2 – 3 fighters</div>
  <div><span class="dot" style="background:#a855f7"></span>4 – 5 fighters</div>
  <div><span class="dot" style="background:#f59e0b"></span>6+ fighters</div>
</div>
<script>
const GYMS   = {geojson};
const COUNTS = {heatmap};

const map = L.map('map').setView([25, -30], 2);

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 19
}}).addTo(map);

// Choropleth — fully filled countries, red intensity by fighter count
const maxCount = Math.max(...Object.values(COUNTS), 1);

function countryColor(name) {{
  const n = COUNTS[name] || 0;
  if (!n) return 'transparent';
  // log scale so single-fighter countries are still visible
  const t = Math.log(n + 1) / Math.log(maxCount + 1);
  const r = 255;
  const g = Math.round(220 * (1 - t));
  const b = Math.round(200 * (1 - t));
  return `rgb(${{r}},${{g}},${{b}})`;
}}

fetch('https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson')
  .then(r => r.json())
  .then(world => {{
    L.geoJSON(world, {{
      style: feature => {{
        const name  = feature.properties.name;
        const count = COUNTS[name] || 0;
        return {{
          fillColor:   countryColor(name),
          fillOpacity: count ? 0.75 : 0,
          color:       count ? 'rgba(255,80,80,0.4)' : 'transparent',
          weight:      count ? 0.8 : 0,
        }};
      }},
      onEachFeature: (feature, layer) => {{
        const name  = feature.properties.name;
        const count = COUNTS[name];
        if (count) {{
          layer.bindTooltip(
            `<strong>${{name}}</strong><br>${{count}} ranked fighter${{count > 1 ? 's' : ''}}`,
            {{ sticky: true, className: 'country-tip' }}
          );
        }}
      }},
    }}).addTo(map);

    // Gym pins added after choropleth so they sit on top
    addGymPins();
  }});

// Gym pins — rendered on top of choropleth
function addGymPins() {{

function markerColor(count) {{
  if (count === 1)  return '#4a9eda';
  if (count <= 3)   return '#ff6b35';
  if (count <= 5)   return '#a855f7';
  return '#f59e0b';
}}

function markerRadius(count) {{
  return Math.min(6 + count * 1.5, 14);
}}

GYMS.features.forEach(feature => {{
  const props  = feature.properties;
  const [lon, lat] = feature.geometry.coordinates;

  L.circleMarker([lat, lon], {{
    radius:      markerRadius(props.count),
    fillColor:   markerColor(props.count),
    color:       'rgba(255,255,255,0.5)',
    weight:      1.5,
    fillOpacity: 0.9,
  }})
  .bindPopup(props.popup, {{ maxWidth: 300 }})
  .addTo(map);
}});
}} // end addGymPins
</script>
</body>
</html>
"""


def write_map(geojson: dict, heatmap: dict, out_path: str) -> None:
    html = MAP_TEMPLATE.format(
        geojson=json.dumps(geojson, separators=(',', ':')),
        heatmap=json.dumps(heatmap, separators=(',', ':')),
    )
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(
        description='Scrape UFC rankings, geocode gyms, generate interactive map.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        '--from-csv', action='store_true',
        help='Skip scraping — build map directly from an existing CSV file',
    )
    ap.add_argument(
        '--top', type=int, default=DEFAULT_TOP_N, metavar='N',
        help=f'Number of ranked fighters per weight class when scraping (default {DEFAULT_TOP_N})',
    )
    ap.add_argument('--csv',     default=os.path.join(DATA_DIR, 'fighter_gyms.csv'))
    ap.add_argument('--geojson', default=os.path.join(DATA_DIR, 'fighter_gyms.geojson'))
    ap.add_argument('--map',     default=MAP_PATH)
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    # ── fast path: build map from existing CSV ─────────────────────────────────
    if args.from_csv:
        print(f"Building map from {args.csv} ...")
        df = pd.read_csv(args.csv)
        geojson = build_geojson(df)
        heatmap = build_country_counts(df)
        with open(args.geojson, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2)
        print(f"  [OK] GeoJSON -> {args.geojson}  ({len(geojson['features'])} gym locations)")
        write_map(geojson, heatmap, args.map)
        print(f"  [OK] Map     -> {args.map}")
        print("\nDone. Open map.html in your browser.")
        return

    # ── full pipeline ──────────────────────────────────────────────────────────

    # 1. scrape rankings
    rankings = scrape_rankings(args.top)

    # 2 + 3. gym lookup + geocode
    print(f"\n[2-3/4] Looking up gyms on Wikipedia and geocoding with Nominatim ...")
    rows: list[dict] = []
    gym_cache: dict[str, tuple] = {}
    all_fighters = [
        (wc, rank, name)
        for wc, ranked in rankings.items()
        for rank, name in ranked.items()
    ]
    total = len(all_fighters)

    for idx, (division, rank, name) in enumerate(all_fighters, 1):
        print(f"  [{idx:>3}/{total}]  {name:<28}  {division} #{rank}")

        gym = get_gym(name)
        time.sleep(0.5)

        if not gym:
            print(f"           -> no gym found on Wikipedia")
            continue

        if gym not in gym_cache:
            lat, lon = geocode(gym)
            gym_cache[gym] = (lat, lon)
            time.sleep(1.1)
        else:
            lat, lon = gym_cache[gym]

        coord_str = f"({lat:.3f}, {lon:.3f})" if lat else "could not geocode"
        print(f"           -> {gym}  {coord_str}")

        rows.append({
            'Division': division,
            'Rank':     rank,
            'Fighter':  name,
            'Gym':      gym,
            'City':     '',
            'Country':  '',
            'Latitude': lat,
            'Longitude': lon,
        })

    # 4. save outputs
    print(f"\n[4/4] Saving outputs ...")

    df = pd.DataFrame(rows)
    df.to_csv(args.csv, index=False)
    print(f"  [OK] CSV     -> {args.csv}  ({len(df)} fighters)")

    geojson = build_geojson(df)
    heatmap = build_country_counts(df)
    with open(args.geojson, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, indent=2)
    print(f"  [OK] GeoJSON -> {args.geojson}  ({len(geojson['features'])} gym locations)")

    write_map(geojson, heatmap, args.map)
    print(f"  [OK] Map     -> {args.map}")

    print()
    print("All done. Open map.html in your browser to view the map.")


if __name__ == '__main__':
    main()
