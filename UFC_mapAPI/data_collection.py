import requests
from bs4 import BeautifulSoup
import googlemaps
import json
from datetime import datetime
import pandas as pd
import numpy as np
import os
import shutil

URL = 'https://www.ufc.com/rankings'
page = requests.get(URL)
soup = BeautifulSoup(page.content, 'html.parser')
weightclass = soup.findAll('div', attrs={'class':'view-grouping'})
api_key = 'AIzaSyBxnrXfcsph_A31SQuiqZSgnV3ySe1gMFk'
map_client = googlemaps.Client(api_key)

Flyweight = weightclass[1].findAll('div', attrs={'class':'views-row'})
Bantamweight = weightclass[2].findAll('div', attrs={'class':'views-row'})
Featherweight = weightclass[3].findAll('div', attrs={'class':'views-row'})
Lightweight = weightclass[4].findAll('div', attrs={'class':'views-row'})
Welterweight = weightclass[5].findAll('div', attrs={'class':'views-row'})
Middleweight = weightclass[6].findAll('div', attrs={'class':'views-row'})
LightHeavyweight = weightclass[7].findAll('div', attrs={'class':'views-row'})
Heavyweight = weightclass[8].findAll('div', attrs={'class':'views-row'})
Strawweight = weightclass[10].findAll('div', attrs={'class':'views-row'})
Flyweight_W = weightclass[11].findAll('div', attrs={'class':'views-row'})
Bantamweight_W = weightclass[12].findAll('div', attrs={'class':'views-row'})

def Parser(weightclass):
    Names = [div.find('a').contents[0] for div in weightclass] 
    Gyms = []
    Names = Names[:11]
    for i in Names:
        name = i.replace(' ','-')
        fighterURL = 'https://www.ufc.com/athlete/' + name
        page = requests.get(fighterURL)
        soup = BeautifulSoup(page.content, 'html.parser')
        gym = soup.findAll('div', attrs={'class':'c-bio__text'})
        Gyms.append(gym[2].text)
    Coords = [{'lat': 0, 'lng': 0} if not map_client.geocode(i) else map_client.geocode(i)[0]['geometry']['location'] for i in Gyms]
    return(Names, Gyms, Coords)

flwroster, flwgyms, flwcoords = Parser(Flyweight)
bwroster, bwgyms, bwcoords = Parser(Bantamweight)
fwroster, fwgyms, fwcoords = Parser(Featherweight)
lwroster, lwgyms, lwcoords = Parser(Lightweight)
wwroster, wwgyms, wwcoords = Parser(Welterweight)
mwroster, mwgyms, mwcoords = Parser(Middleweight)
lhwroster, lhwgyms, lhwcoords = Parser(LightHeavyweight)
hwroster, hwgyms, hwcoords = Parser(Heavyweight)
swroster, swgyms, swcoords = Parser(Strawweight)
wflwroster, wflwgyms, wflwcoords = Parser(Flyweight_W)
wbwroster, wbwgyms, wbwcoords = Parser(Bantamweight_W)

Roster = flwroster + bwroster + fwroster + lwroster + wwroster + mwroster + lhwroster + hwroster + swroster + wflwroster + wbwroster
Gyms = flwgyms + bwgyms + fwgyms + lwgyms + wwgyms + mwgyms + lhwgyms + hwgyms + swgyms + wflwgyms + wbwgyms
Coords = flwcoords + bwcoords + fwcoords + lwcoords + wwcoords + mwcoords + lhwcoords + hwcoords + swcoords + wflwcoords + wbwcoords
Rank = ['C',1,2,3,4,5,6,7,8,9,10]*11

date = datetime.today().strftime('%Y-%m-%d')
product = zip(Rank, Roster, Gyms, Coords)
df = pd.DataFrame(product, columns = ['Rank', 'Name', 'Gym', 'Location'])
df.to_json('data/'+date+'_stats.json',orient='records')

src=open('data/'+date+'_stats.json',"r") 
fline="let dataLocations = "    #Prepending string 
oline=src.readlines() 
#Here, we prepend the string we want to on first line 
oline.insert(0,fline) 
src.close() 
 
src=open('data/'+date+'_stats.json',"w") 
src.writelines(oline) 
src.close() 
shutil.copy('data/'+date+'_stats.json', 'data/locations.js')