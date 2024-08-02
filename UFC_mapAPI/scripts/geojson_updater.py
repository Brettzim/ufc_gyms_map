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


# Aggregate fighters by gym
gyms = defaultdict(lambda: {'fighters': [], 'latitude': None, 'longitude': None})

for weight_class, athletes in rankings.items():
    for rank, details in athletes.items():
        if isinstance(details, dict):  # Ensure details is a dictionary
            gym = details.get('gym', None)
            if gym:
                gyms[gym]['fighters'].append({
                    'Name': details.get('name', 'Unknown'),
                    'Rank': rank,
                    'Weight Class': weight_class
                })
                gyms[gym]['latitude'] = details.get('latitude', None)
                gyms[gym]['longitude'] = details.get('longitude', None)

# Convert aggregated gym data to GeoJSON
def gyms_to_geojson(gyms):
    geojson = {'type': 'FeatureCollection', 'features': []}
    
    for gym, data in gyms.items():
        if data['latitude'] is not None and data['longitude'] is not None:  # Ensure we have valid coordinates
            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [data['longitude'], data['latitude']]
                },
                'properties': {
                    'Gym': gym,
                    'Fighters': data['fighters']
                }
            }
            geojson['features'].append(feature)
    
    return geojson

# Convert gyms to GeoJSON
geojson_data = gyms_to_geojson(gyms)

# Save the GeoJSON to a file
geojson_file_path = f"../geojsons/fighter_gyms_{datetime.today().strftime('%Y-%m-%d')}.geojson"
with open(geojson_file_path, 'w') as f:
    json.dump(geojson_data, f)

print(f"GeoJSON data has been written to {geojson_file_path}")