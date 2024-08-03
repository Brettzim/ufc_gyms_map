import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from collections import defaultdict
import pandas as pd




# Define data import path aka the UFC website's current fighter rankings
URL = 'https://www.ufc.com/rankings'
page = requests.get(URL)
soup = BeautifulSoup(page.content, 'html.parser')
weightclass = soup.findAll('div', attrs={'class':'view-grouping'})

# Read in the master table
master_file_path = '../csvs/fighter_gyms_master.csv'
master_df = pd.read_csv(master_file_path)

# Turn the rankings on the website into a dict
rankings = {}

def extract_athlete_data(row):
    rank = row.select_one('.views-field-weight-class-rank').text.strip()
    name = row.select_one('.views-field-title a').text.strip()
    return rank, name

for grouping in soup.select('.view-grouping'):
    weight_class = grouping.select_one('.view-grouping-header').text.strip()
    rankings[weight_class] = {}
    
    champion_section = grouping.select_one('.rankings--athlete--champion .info h5 a')
    if champion_section:
        champion_name = champion_section.text.strip()
        rankings[weight_class]['Champion'] = champion_name

    rows = grouping.select('tbody tr')
    for row in rows:
        rank, name = extract_athlete_data(row)
        rankings[weight_class][rank] = name

del rankings["Men's Pound-for-Pound Top Rank"]
del rankings["Women's Pound-for-Pound Top Rank"]



# Hydrate the rankings dict with the gym and location data in the master table
master_table_dict = master_df.set_index('Name').to_dict(orient='index')
detailed_rankings = defaultdict(list)

for weight_class, fighters in rankings.items():
    for rank, name in fighters.items():
        if name in master_table_dict:
            gym_info = master_table_dict[name]
            detailed_rankings[gym_info['Gym']].append({
                'name': name,
                'weight': weight_class,
                'rank': rank,
                'latitude': gym_info['latitude'],
                'longitude': gym_info['longitude']
            })

# Convert the dict to GeoJSON
features = []

for gym, fighters in detailed_rankings.items():
    coordinates = [fighters[0]['longitude'], fighters[0]['latitude']]
    fighter_list = "<br>".join([f"{fighter['name']} ({fighter['weight']} - {fighter['rank']})" for fighter in fighters])
    feature = {
        "type": "Feature",
        "properties": {
            "gym_location": gym,
            "fighters": f"<strong>Fighters:</strong><br>{fighter_list}",
            "number_of_fighters": len(fighters)
        },
        "geometry": {
            "type": "Point",
            "coordinates": coordinates
        }
    }
    features.append(feature)

geojson = {
    "type": "FeatureCollection",
    "features": features
}

# Write the dict to a GeoJSON file
geojson_filename = f"../geojsons/fighter_gyms_{datetime.today().strftime('%Y-%m-%d')}.geojson"

with open(geojson_filename, 'w') as file:
    json.dump(geojson, file, indent=2)

print("GeoJSON file created successfully.")
