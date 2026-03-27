# UFC Gyms Map

An interactive map showing where the top 10 ranked UFC fighters in each division currently train. Gym data is AI-researched using the xAI Grok API and plotted on a free, no-API-key Leaflet map.

<img width="2058" height="1130" alt="Screenshot 2026-03-26 233623" src="https://github.com/user-attachments/assets/320702af-86b1-4b3b-9d44-4909b2d0cb69" />

---


## How it works

1. **Scrape** — pulls the current top-10 fighters per division from [ufc.com/rankings](https://www.ufc.com/rankings)
2. **Research** — sends the full fighter list to Grok-3, which looks up each fighter's current training gym and coordinates
3. **Generate** — saves a `fighter_gyms.csv` and builds a self-contained `map.html` ready to open in any browser

---

## Setup

```bash
# Clone and enter the project
git clone https://github.com/Brettzim/ufc_gyms_map.git
cd ufc_gyms_map

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Add your xAI API key to .env
echo XAI_API_KEY=your_key_here > .env
```

Get an xAI API key at [console.x.ai](https://console.x.ai).

---

## Usage

### Refresh the gym data and rebuild the map
```bash
python UFC_mapAPI/scripts/fetch_gyms_claude.py
```
This scrapes the latest UFC rankings, asks Grok to research every gym, archives the old CSV, and rebuilds `map.html`.

### Rebuild the map from the existing CSV (no API call)
```bash
python UFC_mapAPI/scripts/build_data.py --from-csv
```

### Open the map
```bash
# Just open UFC_mapAPI/map.html in your browser — no server needed
```

---

## Project structure

```
ufc_gyms_map/
├── UFC_mapAPI/
│   ├── scripts/
│   │   ├── fetch_gyms_claude.py   # scrape + Grok research + build map
│   │   └── build_data.py          # build map from existing CSV
│   ├── data/
│   │   ├── fighter_gyms.csv       # current gym dataset
│   │   ├── fighter_gyms.geojson   # GeoJSON for the map
│   │   └── archive/               # previous CSVs (date-stamped)
│   └── map.html                   # self-contained interactive map
├── .env                           # XAI_API_KEY (not committed)
├── requirements.txt
└── venv/
```

---

## Map features

- **Dark theme** — CartoDB Dark Matter tiles, no API key required
- **Nationality choropleth** — countries fully filled in red based on how many ranked fighters are from that country. USA, Brazil, and Russia glow the brightest. Hover a country to see the fighter count
- **Gym pins** rendered on top of the choropleth, color-coded by number of ranked fighters at that gym:
  - Blue — 1 fighter
  - Orange — 2–3 fighters
  - Purple — 4–5 fighters
  - Gold — 6+ fighters
- **Click any pin** to see the gym name, city, and all fighters listed with their division and rank

---

## Dependencies

| Package | Purpose |
|---|---|
| `openai` | xAI Grok API (OpenAI-compatible) |
| `requests` + `beautifulsoup4` | Scrape UFC rankings |
| `pandas` | CSV handling |
| `python-dotenv` | Load `.env` API key |
