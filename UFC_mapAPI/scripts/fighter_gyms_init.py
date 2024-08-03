import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import pandas as pd
import re
from urllib.parse import quote
import time

URL = 'https://www.ufc.com/rankings'
page = requests.get(URL)
soup = BeautifulSoup(page.content, 'html.parser')
weightclass = soup.findAll('div', attrs={'class':'view-grouping'})

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

fighter_gyms = {}
for weight_class, fighters in rankings.items():

    names = list(fighters.values())

    for fighter_name in names:
        formatted_name = fighter_name.replace(" ", "_")
        url = f"https://en.wikipedia.org/wiki/{formatted_name}"
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        infobox = soup.find("table", {"class": "infobox"})

        if infobox:
            rows = infobox.find_all("tr")
           
            for row in rows:
                
                header = row.find("th")
                value = row.find("td")

                if header and "Team" in header.text:
                    teams_text = value.get_text()
                    fighter_gyms[fighter_name] = teams_text


df = pd.DataFrame(list(fighter_gyms.items()), columns=['Fighter', 'Gym'])


def extract_gym_parts(gym_string):
    # Remove reference numbers and keep the text within parentheses
    parts = re.split(r'\[\d+\]', gym_string)  # Remove reference numbers
    parts = [part.strip() for part in parts if part.strip()]  # Clean up whitespace and empty parts
    
    gym_parts = []
    for part in parts:
        # Extract text inside parentheses and clean the remaining text
        while '(' in part:
            match = re.search(r'\(.*?\)', part)
            if match:
                gym_name = part[:match.start()].strip()  # Gym name before the parentheses
                parentheses_text = match.group(0)  # Text within parentheses
                gym_parts.append(f"{gym_name} {parentheses_text}".strip())
                part = part[match.end():].strip()  # Remainder of the text
            else:
                gym_parts.append(part.strip())
                break

        if part:
            gym_parts.append(part.strip())
    
    return gym_parts

def clean_timeframe(text):
    # Remove timeframe details like (2018–present)
    return re.sub(r'\(\d{4}–present\)', '', text).strip()

def filter_gym_names(gym_list):
    # Clean timeframe text and then check if 'present' is in any of the gym names
    cleaned_gym_list = [clean_timeframe(gym) for gym in gym_list]
    for gym in cleaned_gym_list:
        if 'present' in gym.lower():
            return gym
    return cleaned_gym_list[-1] if cleaned_gym_list else None

# Apply the extraction function to the DataFrame
df['Clean Gym'] = df['Gym'].apply(extract_gym_parts)
df['Filtered Gym'] = df['Clean Gym'].apply(filter_gym_names)

gym_df = df[['Fighter', 'Filtered Gym']]
display(gym_df) 

# Replace 'YOUR_MAPBOX_ACCESS_TOKEN' with your actual Mapbox access token
ACCESS_TOKEN = ''

def geocode_location_mapbox(location):
    # URL encode the location string
    encoded_location = quote(location)
    
    # Define the Mapbox Geocoding URL
    url = f'https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_location}.json'
    params = {
        'access_token': ACCESS_TOKEN,
        'limit': 1
    }

    response = requests.get(url, params=params)
    
    # Check if the response is valid
    if response.status_code == 200:
        try:
            data = response.json()
            if data['features']:
                # Extract latitude and longitude
                lat = data['features'][0]['geometry']['coordinates'][1]
                lon = data['features'][0]['geometry']['coordinates'][0]
                return lat, lon
            else:
                print(f"No results found for '{location}'")
        except ValueError:
            print("Error decoding JSON response")
    else:
        print(f"HTTP Error: {response.status_code}")
    
    return None, None

# Prepare a list to store the results
results = []

# Iterate over the DataFrame rows
for _, row in gym_df.iterrows():
    fighter = row['Fighter']
    gym_location = row['Filtered Gym']
    
    if gym_location:
        print(f"Geocoding gym location for {fighter}: {gym_location}")
        lat, lon = geocode_location_mapbox(gym_location)
        if lat and lon:
            # Append results to the list
            results.append({
                'Name': fighter,
                'Gym': gym_location,
                'latitude': lat,
                'longitude': lon
            })
        else:
            # Append results with None for coordinates
            results.append({
                'Name': fighter,
                'Gym': gym_location,
                'latitude': None,
                'longitude': None
            })
        # Add a delay to avoid hitting rate limits
        time.sleep(2)

# Convert results to DataFrame
results_df = pd.DataFrame(results)

master_file_path = '../csvs/fighter_gyms_master.csv'
try:
    master_df = pd.read_csv(master_file_path)
except FileNotFoundError:
    master_df = pd.DataFrame(columns=['Name', 'Gym', 'Weight', 'Rank', 'latitude', 'longitude'])

# Find fighters that are not in the master table
new_fighters_df = results_df[~results_df['Name'].isin(master_df['Name'])]
updated_master_df = pd.concat([master_df, new_fighters_df], ignore_index=True)
updated_master_df.to_csv(master_file_path, index=False)

print(f"New fighters have been added to {master_file_path}")