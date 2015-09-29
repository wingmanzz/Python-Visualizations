import pandas as pd
import json
import vincent
from progressbar import ProgressBar
import os
import sys
import operator
import requests
from math import log10, floor

def iso3tocountry(iso3):
    if (iso3 == 'XXK'):
        return "Kosovo"
    if (iso3 == 'MYT'):
        return "Mayotte"
    if (iso3 == 'TKL'):
        return "Tokelau"
    if (iso3 == 'NIU'):
        return "Niue"
    if (iso3 == 'COK'):
        return "Cook Islands"
    if (iso3 == 'AIA'):
        return "Anguilla"
    if (iso3 == 'COD'):
        return "Democratic Republic of Congo"
    url = 'http://api.worldbank.org/countries/'+iso3+'?format=json'
    r = requests.get(url)
    data = json.loads(str(r.content))
    s = data[1][0]['name']
    s = s.replace("\'","'\\''")
    return s


# Adds countries that have not received $ to the list so that they can be displayed on the map
def addNonFlowCountries(donor_dict, world):
    for country in world['objects']['world-countries']['geometries']:
        if country['id'] not in donor_dict:
            donor_dict[country['id']] = 0.0
    return donor_dict

# Creates a string of years to search in the api
def getYearString(start_year, finish_year):
    result = ''
    while start_year < finish_year:
        result += str(start_year)
        result += ','
        start_year += 1
    result += str(finish_year)
    return result

r = requests.get('https://raw.githubusercontent.com/wingmanzz/Python-Visualizations/master/assets/world-countries.topo.json')
get_id = json.loads(str(r.content))

# create a dataframe of iso-3 codes in for use in builiding the map
geometries = get_id['objects']['world-countries']['geometries']
iso_codes = [x['id'] for x in geometries]
country_df = pd.DataFrame({'iso_a3': iso_codes}, dtype=str)

# First cmd line parameter is the organization id as specified by the organization id numbers on
start_year = int(sys.argv[1])
# Third cmd line parameter is the end year for the project data
end_year = int(sys.argv[2])

year_range = getYearString(start_year, end_year)
organizations_url = 'http://api.aiddata.org/data/origin/organizations?'
r = requests.get(organizations_url)
json_orgs = json.loads(str(r.content))

#receiver orgs
rcv_url = 'http://api.aiddata.org/data/paDestination/organizations?'
r = requests.get(rcv_url)
rcv_orgs = json.loads(str(r.content))

#iso2 to iso3 translate
iso_url = 'https://github.com/wingmanzz/Python-Visualizations/raw/master/assets/countries.json'
r = requests.get(iso_url)
isos = json.loads(str(r.content))

# Finds the organization based on the id
for org in json_orgs['hits']:
    donating_org = org['name']
    organization_id = org['id']
    url = 'http://api.aiddata.org/flows/destination?fo=' + str(org['id'])+'&y=' + str(year_range)
    print 'Creating map for ' + donating_org

    r = requests.get(url)
    receiver_list = json.loads(str(r.content))
    num_projects = receiver_list['item_count']

    # if we have projects, do it!
    if num_projects > 0:
        count = 0
        totamt = 0
        country_dict = {}

        # Iterates over the projects from the AidData
        for country in receiver_list['items']:
            receiver_o = country['source']["_id"]
            for found in rcv_orgs['hits']:
                if found['id'] == receiver_o:
                    iso2 = found['iso2']
                    if iso2 in isos:
                        receiver = isos[iso2]
                        amount = country['total']
                        totamt += amount
                        if receiver not in country_dict:
                            country_dict[receiver] = amount
                        else:
                            country_dict[receiver] += amount

        #sort by amount
        dict_values = country_dict
        sorted_x = sorted(dict_values.items(), key=operator.itemgetter(1), reverse=True)

        geo_data = [{'name': 'countries',
                     'url': 'https://raw.githubusercontent.com/wingmanzz/Python-Visualizations/master/assets/world-countries.topo.json',
                     'feature': 'world-countries'}]


        country_dict = addNonFlowCountries(country_dict, get_id)

        receiving_df = pd.DataFrame(list(country_dict.iteritems()), columns=['iso_a3', 'total_received'])

        merged = pd.merge(receiving_df, country_df, on='iso_a3', how='inner')

        # Uses vincent to create a map in vega format
        vis = vincent.Map(data=merged, geo_data=geo_data, brew="Greens", projection='times', scale=250,
                  data_bind='total_received', data_key='iso_a3',
                  map_key={'countries': 'id'})
        vis.padding = {'top': 210, 'left': 80, 'bottom': 250, 'right': 80}

        json_file_name = donating_org.replace(' ', '_') + '_donations.json'
        png_file_name = donating_org.replace(' ', '_') + '_donations.png'
        png_file_name = png_file_name.replace('(','_')
        json_file_name = json_file_name.replace('(','_')
        png_file_name = png_file_name.replace(')','_')
        json_file_name = json_file_name.replace(')','_')
        png_file_name = png_file_name.replace('&','_')
        json_file_name = json_file_name.replace('&','_')
        png_file_name = png_file_name.replace(',','_')
        json_file_name = json_file_name.replace(',','_')
        json_file_name = json_file_name.encode('ascii', 'ignore')
        png_file_name = png_file_name.encode('ascii', 'ignore')
        donating_org = donating_org.encode('ascii', 'ignore')
        vis.to_json(json_file_name)
        cmd = "vg2png output/" + json_file_name + " output/" + png_file_name
        # Transforms the vega json into a donor map image using the vg2png command line function
        os.system(cmd)

        donating_org = donating_org.replace("'","")

        max = 0
        if (len(sorted_x) > 0):
            max = sorted_x[0][1]
        os.system("convert " + png_file_name + " assets/green_ramp_donor_profiles.png -geometry +45+435 -composite output/" + png_file_name)
        os.system("convert " + png_file_name + " -pointsize 12 -weight Bold -annotate +45+425 'Commitments (USD 2011)' output/" + png_file_name)
        os.system("convert " + png_file_name + " -pointsize 12 -annotate +88+443 '" + "{:,.2f}".format(max) + "' -annotate +88+653 '0' output/" + png_file_name)
        #sets 'top 10 partner countries' text
        os.system("convert " + png_file_name + " -pointsize 20 -annotate +50+720 'Top 10 Partner Countries' output/" + png_file_name)

        #function to round to nearest tenth of a mil
        def round_to_1(x):
            x = round(x)
            x = x / 1000000
            x = round(x,1)
            return str(x) + " million"

        #sets offset for top 10 partner countries chart
        offset = 750
        #loop generates 2 columns of 5 rows
        for i in range(0, len(sorted_x)):
            name = iso3tocountry(sorted_x[i][0])
            if i == 10:
                break
            if i < 5:
                x_coord = 50
            else:
                x_coord = 600
            y_coord = offset + ((i % 5) * 30)
            if (totamt > 0):
                millions = str(round((sorted_x[i][1] / totamt * 100), 1))
            else:
                millions = "0.0"
            #generates first part of column (the country name)
            os.system("convert output/" + png_file_name + " -pointsize 20 -fill '#75B654' -annotate +" + str(x_coord) + "+" + str(y_coord) + " '" + str(i+1) + ". " + name + "' " + png_file_name)
            os.system("convert output/" + png_file_name + " -pointsize 20 -annotate +" + str(x_coord) + "+" + str(y_coord) + " '" + str(i+1) + ". " + "' " + png_file_name)
            #generates second part of column (the percentage and dollar ammount)
            os.system("convert output/" + png_file_name + " -pointsize 20 -annotate +" + str(x_coord+250) + "+" + str(y_coord) + " '(" + millions + "\%, " + round_to_1(sorted_x[i][1]) + " USD)' " + png_file_name)
