import pandas as pd
import geopandas as gpd

print("--- STARTING PHASE 2: DEMAND BASELINE ---")

# =======================================================
# 1. LOAD & FILTER TAX PARCELS (Dasymetric Prep)
# =======================================================
print("1. Loading and filtering Tax Parcels...")
gdf_parcels = gpd.read_file('Tax_Parcels_2025.shp')

# IMPORTANT: You must inspect your parcel columns to find the zoning/land use column.
# Common names are 'LUC', 'LANDUSE', 'CLASS', or 'ZONING'.
# Let's assume it's called 'LUC' (Land Use Code) and residential codes start with 'R' or '1'.
# We filter to ONLY keep residential parcels (Single Family, Multi-Family, Apartments)
residential_keywords = ['R', 'RES', 'APARTMENT', 'CONDO', 'SINGLE FAMILY', 'MULTI']
# Create a mask to filter (Adjust 'LUC' to your actual column name!)
# If your data uses codes instead of words (e.g., 100 for residential), adjust the logic.
gdf_res_parcels = gdf_parcels[gdf_parcels['LUC'].astype(str).str.contains('|'.join(residential_keywords), case=False, na=False)].copy()

# Calculate the area (square footage) of each residential parcel
# We use this as the weight to distribute the population
gdf_res_parcels['parcel_area_sqft'] = gdf_res_parcels.geometry.area

print(f"Filtered down to {len(gdf_res_parcels)} residential parcels.")


# =======================================================
# 2. LOAD & ENRICH CENSUS DATA (Segmentation)
# =======================================================
print("2. Loading Census Data and applying segmentation...")
gdf_census = gpd.read_file('lila_halfmi_census.shp')

# (Assuming you already ran your Phase 1 script, or we apply a basic version here)
gdf_census['MdnFmlI'] = pd.to_numeric(gdf_census['MdnFmlI'], errors='coerce').fillna(0)
gdf_census['PvrtyRt'] = pd.to_numeric(gdf_census['PvrtyRt'], errors='coerce').fillna(0)
gdf_census['POP10'] = pd.to_numeric(gdf_census['POP10'], errors='coerce').fillna(0)

# MOCK DATA INJECTION: Assuming you merged ACS data for Seniors and Vehicles
# If you haven't, you'll need to join that data here. For now, we simulate it if missing.
if 'Pct_Senior' not in gdf_census.columns:
    print("Warning: Pct_Senior missing. Using placeholder data.")
    gdf_census['Pct_Senior'] = 0.15 # Placeholder
if 'Pct_No_Veh' not in gdf_census.columns:
    print("Warning: Pct_No_Veh missing. Using placeholder data.")
    gdf_census['Pct_No_Veh'] = 0.10 # Placeholder


# --- APPLY SEGMENTATION LOGIC ---
def segment_tract(row):
    # 1. Economic Severity (From your Phase 1 notes)
    if row['MdnFmlI'] < 35000 or row['PvrtyRt'] > 30:
        econ_zone = "Zone 1 (Severe)"
    elif row['MdnFmlI'] <= 60000:
        econ_zone = "Zone 2 (Moderate)"
    else:
        econ_zone = "Zone 3 (Secure)"
        
    # 2. Mobility & Age Rules
    # Default walking access is 0.5 miles (2640 feet)
    walk_limit_miles = 0.5
    
    # If a neighborhood is >25% seniors, cut the required walking distance to 0.3 miles
    if row['Pct_Senior'] > 0.25:
        walk_limit_miles = 0.3
        
    # If >20% of the neighborhood has no car, flag them as Transit Dependent
    # (Meaning the 0.5 mile rule is STRICT, they cannot drive to a store)
    is_transit_dependent = True if row['Pct_No_Veh'] > 0.20 else False
    
    return pd.Series([econ_zone, walk_limit_miles, is_transit_dependent])

# Apply the logic to create new columns
gdf_census[['Economic_Zone', 'Required_Walk_Miles', 'Transit_Dependent']] = gdf_census.apply(segment_tract, axis=1)


# =======================================================
# 3. THE DASYMETRIC SPATIAL JOIN
# =======================================================
print("3. Executing Dasymetric Spatial Join...")

# Ensure both maps use the same coordinate reference system (CRS)
gdf_res_parcels = gdf_res_parcels.to_crs(gdf_census.crs)

# Spatial Join: Assigns every residential parcel to its parent census tract
# 'how=inner' means we only keep parcels that fall inside our Atlanta census tracts
gdf_dasymetric = gpd.sjoin(gdf_res_parcels, gdf_census, how="inner", predicate="intersects")

# --- THE POPULATION APPORTIONMENT MATH ---
# A. Find the total residential area inside each census tract
tract_res_area = gdf_dasymetric.groupby('tract')['parcel_area_sqft'].sum().reset_index()
tract_res_area.rename(columns={'parcel_area_sqft': 'tract_total_res_sqft'}, inplace=True)

# B. Merge that total back to the individual parcels
gdf_dasymetric = gdf_dasymetric.merge(tract_res_area, on='tract', how='left')

# C. Calculate the percentage of the tract's residential space that THIS parcel takes up
gdf_dasymetric['area_ratio'] = gdf_dasymetric['parcel_area_sqft'] / gdf_dasymetric['tract_total_res_sqft']

# D. Multiply the ratio by the tract's total population to get the PARCEL population
gdf_dasymetric['parcel_population'] = (gdf_dasymetric['area_ratio'] * gdf_dasymetric['POP10']).round(0)


# =======================================================
# 4. CLEANUP AND EXPORT
# =======================================================
print("4. Saving High-Resolution Demand Baseline...")

# Keep only the columns we actually need for the next phase
final_columns = [
    'geometry', 'parcel_population', 'Economic_Zone', 
    'Required_Walk_Miles', 'Transit_Dependent', 'MdnFmlI', 'PvrtyRt'
]
# Add whatever your Parcel ID column is called (e.g., 'PARCEL_ID' or 'PIN')
# final_columns.insert(1, 'PARCEL_ID') 

gdf_final_demand = gdf_dasymetric[final_columns]

# Save as a GeoPackage (.gpkg is much faster and cleaner than .shp for large datasets)
gdf_final_demand.to_file("Atlanta_Demand_Baseline_2025.gpkg", driver="GPKG")

print("SUCCESS! You have converted general census data into building-level population dots.")
print(gdf_final_demand[['parcel_population', 'Economic_Zone', 'Required_Walk_Miles']].head())