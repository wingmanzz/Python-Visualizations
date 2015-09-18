import pandas as pd
import json
import vincent
import urllib2
from progressbar import ProgressBar
import os
import sys
from StringIO import StringIO
import gzip
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
    url = 'http://api.worldbank.org/countries/'+iso3+'?format=json'
    r = requests.get(url)
    data = json.loads(str(r.content))
    print iso3
    s = data[1][0]['name']
    s = s.replace("\'","'\\''")
    return s

   
    
# Gets project data from AidData project api for an organization indicated by its AidData api id
def getProjectData(index, organization, years):
    url = 'http://api.aiddata.org/aid/project?size=50&src=1,2,3,4,5,6,7,3249668&fo=' + str(organization) + '&from=' + str(index) + '&y=' + str(years)
    
    request = urllib2.Request(url)
    
    #we must check the return to see if its gzipped, some api calls return gzip
    request.add_header('Accept-encoding', 'gzip')
    response = urllib2.urlopen(request)
    if response.info().get('Content-Encoding') == 'gzip':
        buf = StringIO(response.read())
        f = gzip.GzipFile(fileobj=buf)
        data = f.read()
    else:
    	data = response.read()

    result = json.loads(data)
    return result

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

request = urllib2.urlopen('https://raw.githubusercontent.com/wingmanzz/Python-Visualizations/master/world-countries.topo.json')
get_id = json.load(request)

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
json_orgs = json.load(urllib2.urlopen(organizations_url))

# Finds the organization based on the id
for org in json_orgs['hits']:
	donating_org = org['name']
	organization_id = org['id']
	url = 'http://api.aiddata.org/aid/project?size=50&fo=' + str(org['id'])+'&y=' + str(year_range)
	print url
	print 'Creating map for ' + donating_org

	json_result = json.load(urllib2.urlopen(url))
	num_projects = json_result['project_count']
	
	if num_projects > 0:
		count = 0
		totamt = 0
		country_dict = {}
		pbar = ProgressBar(maxval=num_projects).start()

		# Iterates over the projects from the AidData api in chunks of 50, the max size allowed by the api
		while (count < num_projects):
			project_info = getProjectData(count, organization_id, year_range)
			for project in project_info['items']:
				# Only looks at projects that have transaction values
				if 'transactions' in project:
					for transactions in project['transactions']:
						# Ignores projects that don't indicate a recipient country
						if 'tr_receiver_country' in transactions:
							if 'iso3' in transactions['tr_receiver_country']:
								receiver = transactions['tr_receiver_country']['iso3']
								amount = transactions['tr_constant_value']
								totamt += amount
								if receiver not in country_dict:
									country_dict[receiver] = amount
								else:
									country_dict[receiver] += amount
			count += 50
			if(count < num_projects):
				pbar.update(count)
			else:
				to_add = num_projects - (count - 50)
				pbar.update(to_add)

		pbar.finish()

	#sort by amount
	dict_values = country_dict
	sorted_x = sorted(dict_values.items(), key=operator.itemgetter(1), reverse=True)

	geo_data = [{'name': 'countries',
				 'url': 'https://raw.githubusercontent.com/wingmanzz/Python-Visualizations/master/world-countries.topo.json',
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
	vis.to_json(json_file_name)
	# Transforms the vega json into a donor map image using the vg2png command line function
	os.system("vg2png " + json_file_name + " " + png_file_name)

	donating_org = donating_org.replace("'","")

	#sets title
	os.system("convert " + png_file_name + " -pointsize 26 -gravity north -annotate +10+33 'Distribution of " + donating_org + "'\\''" + "s Official Development Assistance (ODA), " + str(start_year) + "-" + str(end_year) + "' "  + png_file_name)

	#sets 'top 10 partner countries' text
	os.system("convert " + png_file_name + " -pointsize 22 -annotate +50+720 'Top 10 Partner Countries' " + png_file_name)

	#function to round to nearest tenth of a mil
	def round_to_1(x):
		#x = round(x, -int(floor(log10(x))))
		#return x
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
		#generates first part of column (the country name)
		os.system("convert " + png_file_name + " -pointsize 20 -fill '#75B654' -annotate +" + str(x_coord) + "+" + str(y_coord) + " '" + str(i+1) + ". " + name + "' " + png_file_name)
		os.system("convert " + png_file_name + " -pointsize 20 -annotate +" + str(x_coord) + "+" + str(y_coord) + " '" + str(i+1) + ". " + "' " + png_file_name)
		#generates second part of column (the percentage and dollar ammount)
		os.system("convert " + png_file_name + " -pointsize 20 -annotate +" + str(x_coord+250) + "+" + str(y_coord) + " '(" + str(round((sorted_x[i][1] / totamt * 100), 1)) + "\%, " + round_to_1(sorted_x[i][1]) + " USD)' " + png_file_name)
