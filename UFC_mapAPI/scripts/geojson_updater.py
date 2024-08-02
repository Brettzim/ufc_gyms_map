import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from collections import defaultdict
import pandas as pd

URL = 'https://www.ufc.com/rankings'
page = requests.get(URL)
soup = BeautifulSoup(page.content, 'html.parser')
weightclass = soup.findAll('div', attrs={'class':'view-grouping'})

rankings = {}

# Function to extract athlete data from a row
def extract_athlete_data(row):
    rank = row.select_one('.views-field-weight-class-rank').text.strip()
    name = row.select_one('.views-field-title a').text.strip()
    return rank, name

# Iterate over all view groupings (weight classes)
for grouping in soup.select('.view-grouping'):
    weight_class = grouping.select_one('.view-grouping-header').text.strip()
    rankings[weight_class] = {}
    
    # Extract champion if present
    champion_section = grouping.select_one('.rankings--athlete--champion .info h5 a')
    if champion_section:
        champion_name = champion_section.text.strip()
        rankings[weight_class]['Champion'] = champion_name
    
    # Extract other athletes
    rows = grouping.select('tbody tr')
    for row in rows:
        rank, name = extract_athlete_data(row)
        rankings[weight_class][rank] = name

del rankings["Men's Pound-for-Pound Top Rank"]
del rankings["Women's Pound-for-Pound Top Rank"]

# Read the master table
master_file_path = '../csvs/fighter_gyms_master.csv'
master_df = pd.read_csv(master_file_path)

# Create a dictionary from the DataFrame
fighter_gym_dict = master_df.set_index('Name').to_dict(orient='index')

# Update rankings dictionary with gym information from master_df
for weight_class, athletes in rankings.items():
    for rank, fighter in athletes.items():
        if fighter in fighter_gym_dict:
            gym_info = fighter_gym_dict[fighter]
            rankings[weight_class][rank] = {
                'name': fighter,
                'gym': gym_info['Gym'],
                'latitude': gym_info['latitude'],
                'longitude': gym_info['longitude']
            }

# Group fighters by gym
gym_dict = defaultdict(lambda: {'latitude': None, 'longitude': None, 'fighters': []})

for weight_class, fighters in rankings.items():
    for rank, fighter_info in fighters.items():
        gym = fighter_info['gym']
        gym_dict[gym]['latitude'] = fighter_info['latitude']
        gym_dict[gym]['longitude'] = fighter_info['longitude']
        gym_dict[gym]['fighters'].append(f"{fighter_info['name']} ({weight_class} - {rank})")

# Generate GeoJSON features
features = []
for gym, info in gym_dict.items():
    features.append({
        "type": "Feature",
        "properties": {
            "gym_location": gym,
            "fighters": "<br>".join(info['fighters'])
        },
        "geometry": {
            "type": "Point",
            "coordinates": [
                info['longitude'],
                info['latitude']
            ]
        }
    })

# Create GeoJSON structure
geojson = {
    "type": "FeatureCollection",
    "features": features
}


geojson_filename = f"../geojsons/fighter_gyms_{datetime.today().strftime('%Y-%m-%d')}.geojson"
with open(geojson_filename, 'w') as file:
    json.dump(geojson, file, indent=2)

print(f"GeoJSON file '{geojson_filename}' created successfully.")