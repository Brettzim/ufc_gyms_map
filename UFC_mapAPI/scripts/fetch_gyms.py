#!/usr/bin/env python3
"""
fetch_gyms_claude.py
====================
Uses the xAI Grok API (with live web search) to research the current training gym
and coordinates for every top-10 UFC fighter, then writes a map-ready CSV.

Steps:
  1. Scrape ufc.com/rankings for current top-10 fighters per division
  2. Archive the existing data/fighter_gyms.csv with today's date
  3. Call Grok (grok-3 + live web search) with the full fighter list
  4. Parse the CSV response and save to data/fighter_gyms.csv
  5. Auto-rebuild the map

Usage:
    python scripts/fetch_gyms_claude.py

Requirements:
    pip install openai requests beautifulsoup4 pandas python-dotenv
    Set XAI_API_KEY in .env:
        XAI_API_KEY=your_key_here
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# ── paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.join(SCRIPT_DIR, '..')
DATA_DIR    = os.path.join(BASE_DIR, 'data')
ARCHIVE_DIR = os.path.join(DATA_DIR, 'archive')
CSV_PATH    = os.path.join(DATA_DIR, 'fighter_gyms.csv')

# Load .env from project root (two levels up from this script)
load_dotenv(os.path.join(SCRIPT_DIR, '..', '..', '.env'))

# ── constants ──────────────────────────────────────────────────────────────────
UFC_URL  = 'https://www.ufc.com/rankings'
HEADERS  = {'User-Agent': 'Mozilla/5.0 (compatible; ufc-gyms-map/1.0)'}
TOP_N    = 10
MODEL    = 'grok-3'
XAI_BASE = 'https://api.x.ai/v1'


# ══════════════════════════════════════════════════════════════════════════════
# Step 1 — Scrape UFC rankings
# ══════════════════════════════════════════════════════════════════════════════

def scrape_rankings() -> list[dict]:
    """Return [{division, rank, name}, ...] for top-10 + champion per division."""
    print('[1/4] Scraping UFC rankings from ufc.com/rankings ...')
    resp = requests.get(UFC_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, 'html.parser')

    fighters = []
    for group in soup.select('.view-grouping'):
        division = group.select_one('.view-grouping-header').text.strip()
        if 'pound-for-pound' in division.lower():
            continue

        champ = group.select_one('.rankings--athlete--champion .info h5 a')
        if champ:
            fighters.append({'division': division, 'rank': 'C', 'name': champ.text.strip()})

        for row in group.select('tbody tr'):
            rank_el = row.select_one('.views-field-weight-class-rank')
            name_el = row.select_one('.views-field-title a')
            if not rank_el or not name_el:
                continue
            rank = rank_el.text.strip()
            try:
                if int(rank) <= TOP_N:
                    fighters.append({
                        'division': division,
                        'rank':     rank,
                        'name':     name_el.text.strip(),
                    })
            except ValueError:
                pass

    print(f'     {len(fighters)} fighters across '
          f'{len(set(f["division"] for f in fighters))} divisions')
    return fighters


# ══════════════════════════════════════════════════════════════════════════════
# Step 2 — Archive existing CSV
# ══════════════════════════════════════════════════════════════════════════════

def archive_existing_csv() -> None:
    """Move data/fighter_gyms.csv -> data/archive/fighter_gyms_YYYY-MM-DD.csv"""
    if not os.path.exists(CSV_PATH):
        print('[2/4] No existing CSV to archive.')
        return
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    date_str     = datetime.today().strftime('%Y-%m-%d')
    archive_path = os.path.join(ARCHIVE_DIR, f'fighter_gyms_{date_str}.csv')

    counter = 1
    while os.path.exists(archive_path):
        archive_path = os.path.join(ARCHIVE_DIR, f'fighter_gyms_{date_str}_{counter}.csv')
        counter += 1

    shutil.move(CSV_PATH, archive_path)
    print(f'[2/4] Archived old CSV -> {archive_path}')


# ══════════════════════════════════════════════════════════════════════════════
# Step 3 — Call Grok API with live web search
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_TEMPLATE = """\
You are building a dataset of UFC fighter training gyms for an interactive Leaflet map.

Here is the current list of UFC ranked fighters (top 10 per division + champions):

{fighter_list}

GOAL: For each fighter above, find:
  1. Their CURRENT primary MMA training gym name
  2. The gym's city
  3. The gym's country
  4. The gym's latitude and longitude (precise — use the actual gym building location)

CONTEXT:
- Many gyms share the same name worldwide. Always cross-reference the fighter's known
  nationality/base location to identify the correct gym.
- Search the web for each fighter. Wikipedia is a good first source, but also check
  MMA news sites, fighter social media, and gym websites.
- Use the fighter's most CURRENT gym — fighters change teams frequently.
- Coordinates must be for the actual gym, not just the city center.

ACTION: Research every fighter on the list using live web search and return the results.

OUTPUT FORMAT — return ONLY the raw CSV, nothing else (no markdown, no code fences,
no commentary before or after). Start immediately with the header row:

Division,Rank,Fighter,Gym,City,Country,Latitude,Longitude,Nationality

Where:
  - Division    = the UFC weight class (e.g. Lightweight, Women's Strawweight)
  - Rank        = C (Champion), IC (Interim Champion), or 1-10
  - Fighter     = exact fighter name as given above
  - Gym         = current primary training gym name
  - City        = city where the gym is located
  - Country     = country where the gym is located
  - Latitude    = decimal degrees for the gym (e.g. 37.3382)
  - Longitude   = decimal degrees for the gym (e.g. -121.8863)
  - Nationality = fighter's country of birth / citizenship (e.g. USA, Brazil, Russia)
"""


def call_grok(fighters: list[dict]) -> str:
    """Stream a Grok API call with live web search and return the full response."""
    api_key = os.environ.get('XAI_API_KEY', '').strip()
    if not api_key:
        print('ERROR: XAI_API_KEY environment variable is not set.')
        print('  Add it to your .env file:  XAI_API_KEY=your_key_here')
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=XAI_BASE)

    fighter_list_text = '\n'.join(
        f'  - {f["name"]} ({f["division"]}, rank {f["rank"]})'
        for f in fighters
    )
    prompt = PROMPT_TEMPLATE.format(fighter_list=fighter_list_text)

    print(f'[3/4] Calling {MODEL} ...')
    print('      (This may take a few minutes)\n')

    text_chunks: list[str] = []
    done = threading.Event()
    start_time = time.time()

    def heartbeat() -> None:
        while not done.is_set():
            done.wait(30)
            if not done.is_set():
                elapsed = int(time.time() - start_time)
                print(f'\n  ... still running ({elapsed}s elapsed) ...\n', flush=True)

    timer = threading.Thread(target=heartbeat, daemon=True)
    timer.start()

    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                text_chunks.append(delta.content)
                print(delta.content, end='', flush=True)
    finally:
        done.set()

    elapsed = int(time.time() - start_time)
    print(f'\n\n      Done in {elapsed}s.')
    return ''.join(text_chunks)


# ══════════════════════════════════════════════════════════════════════════════
# Step 4 — Parse CSV from response
# ══════════════════════════════════════════════════════════════════════════════

def parse_csv(text: str) -> pd.DataFrame:
    """Extract CSV rows from Grok's response and return as a DataFrame."""
    # Strip markdown fences if the model added them despite instructions
    text = re.sub(r'```(?:csv)?\s*', '', text).strip()

    csv_match = re.search(r'(Division,Rank,Fighter\b.*)', text, re.IGNORECASE | re.DOTALL)
    if not csv_match:
        raise ValueError('Could not find CSV header in response.')

    lines    = [l for l in csv_match.group(1).splitlines() if l.strip()]
    csv_text = '\n'.join(lines)

    df = pd.read_csv(StringIO(csv_text))

    required = {'Division', 'Rank', 'Fighter', 'Gym', 'City', 'Country', 'Latitude', 'Longitude'}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f'Missing columns in CSV: {missing}')

    return df


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    fighters = scrape_rankings()
    archive_existing_csv()
    raw_response = call_grok(fighters)

    print('[4/4] Parsing and saving CSV ...')
    try:
        df = parse_csv(raw_response)
        df.to_csv(CSV_PATH, index=False)
        print(f'     Saved {len(df)} fighters -> {CSV_PATH}')
    except Exception as exc:
        raw_path = os.path.join(DATA_DIR, 'grok_raw_response.txt')
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(raw_response)
        print(f'ERROR: Could not parse CSV: {exc}')
        print(f'       Raw response saved to {raw_path} for inspection.')
        sys.exit(1)

    print('\nRebuilding map from new CSV ...')
    build_script = os.path.join(SCRIPT_DIR, 'build_data.py')
    subprocess.run([sys.executable, build_script, '--from-csv'], check=True)


if __name__ == '__main__':
    main()
