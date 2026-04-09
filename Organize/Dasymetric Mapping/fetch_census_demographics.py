import pandas as pd
import geopandas as gpd
import requests

print("1. Querying the US Census Bureau API...")

# The endpoint for the ACS 5-Year Data Profiles
url = "https://api.census.gov/data/2022/acs/acs5/profile"

# Set up our query parameters
params = {
    # The columns we want to fetch
    "get": "NAME,DP05_0001E,DP05_0024E,DP04_0046E,DP04_0058E",
    # We want every tract (*) inside Georgia (13) for Fulton (121) and DeKalb (089)
    "for": "tract:*",
    "in": "state:13 county:121,089"
}

# Make the request to the Census API
response = requests.get(url, params=params)

if response.status_code == 200:
    print("Data retrieved successfully!")
    # The API returns a list of lists. The first list is the column headers.
    data = response.json()
    headers = data.pop(0)
    df_acs = pd.DataFrame(data, columns=headers)
else:
    print("Error querying Census API:", response.text)
    exit()

print("2. Cleaning and calculating percentages...")

# Convert the API strings to numeric values for math
numeric_cols = ['DP05_0001E', 'DP05_0024E', 'DP04_0046E', 'DP04_0058E']
for col in numeric_cols:
    # Coerce errors to NaN and fill with 0 to prevent division errors
    df_acs[col] = pd.to_numeric(df_acs[col], errors='coerce').fillna(0)

# Calculate Percentage of Seniors (65+)
# (Seniors / Total Population)
df_acs['Pct_Senior'] = (df_acs['DP05_0024E'] / df_acs['DP05_0001E']).fillna(0)

# Calculate Percentage of Zero-Vehicle Households
# (No Vehicle HHs / Total HHs)
df_acs['Pct_No_Veh'] = (df_acs['DP04_0058E'] / df_acs['DP04_0046E']).fillna(0)

# Create a master 11-digit GEOID to match your shapefile
# GEOID = State (2) + County (3) + Tract (6)
df_acs['GEOID'] = df_acs['state'] + df_acs['county'] + df_acs['tract']

# Keep only the columns we need
df_new_demographics = df_acs[['GEOID', 'Pct_Senior', 'Pct_No_Veh']].copy()

print(f"Processed {len(df_new_demographics)} census tracts.")


print("3. Merging with existing LILA Shapefile...")

# Load your existing baseline data
gdf_lila = gpd.read_file(r'D:\LZY\Projects\investAtlanta26\Organize\Economic Access\lila_halfmi_census.shp')

# IMPORTANT: Check what the tract ID column is named in your LILA dataset.
# It is usually called 'tract', 'GEOID', or 'CensusTract'. 
# We need to make sure both sides are formatted as strings to match perfectly.
# Assuming your LILA file calls it 'tract':
gdf_lila['tract'] = gdf_lila['tract'].astype(str)


# Perform the merge directly on the 'tract' column!
gdf_enriched = gdf_lila.merge(
    df_new_demographics, 
    on='tract',       # Since both files call it 'tract', we just use 'on'
    how='left'
)

# Export the updated shapefile
output_file = 'lila_halfmi_census_enriched.shp'
gdf_enriched.to_file(output_file)

print(f"SUCCESS! Enriched shapefile saved as '{output_file}'")
print("\nSample of the new data:")
print(gdf_enriched[['tract', 'Pct_Senior', 'Pct_No_Veh']].head())

