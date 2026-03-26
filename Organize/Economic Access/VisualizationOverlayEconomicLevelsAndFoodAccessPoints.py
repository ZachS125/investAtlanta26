import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np # Used to generate our temporary mock price data

print("1. Loading the Base Layer (Census Tracts)...")
# Load your census shapefile
gdf_census = gpd.read_file(r'D:\LZY\Projects\investAtlanta26\Organize\Economic Access\lila_halfmi_census.shp')
gdf_census['PvrtyRt'] = pd.to_numeric(gdf_census['PvrtyRt'], errors='coerce')


print("2. Loading the Point Layer (Grocery Stores)...")
# Load the CSV of your filtered stores
df_stores = pd.read_csv('high_confidence_fresh_food.csv')

# Drop any rows that are missing latitude or longitude so it doesn't crash
df_stores = df_stores.dropna(subset=['latitude', 'longitude'])

# CONVERT CSV TO A GEODATAFRAME
# We tell geopandas which columns hold the X (longitude) and Y (latitude) coordinates.
# We set the initial CRS to EPSG:4326, which is standard GPS format.
gdf_stores = gpd.GeoDataFrame(
    df_stores, 
    geometry=gpd.points_from_xy(df_stores.longitude, df_stores.latitude),
    crs="EPSG:4326"
)

# ALIGN THE MAPS
# This is the most important step! Make the stores match the census map projection.
gdf_stores = gdf_stores.to_crs(gdf_census.crs)


print("3. Adding Mock Price Categories...")
# Let's randomly assign cheap, moderate, or expensive to test our color coding
# (You will delete this block once you have real price data)
np.random.seed(42) # Keeps the random assignment consistent
price_categories = ['1 - Affordable (<$10)', '2 - Moderate ($10-$15)', '3 - Expensive (>$15)']
gdf_stores['price_tier'] = np.random.choice(price_categories, size=len(gdf_stores))


print("4. Drawing the Stacked Map...")
# Set up the Canvas
fig, ax = plt.subplots(figsize=(18, 16))

# --- LAYER 1: THE BASE MAP (Census Tracts) ---
gdf_census.plot(
    column='PvrtyRt',         
    cmap='Blues',             # Changed to a Blue gradient
    edgecolor='darkgrey',        
    linewidth=0.5,            
    missing_kwds={'color': 'white'}, 
    alpha=0.75,               # Slightly less transparent so the blue pops
    legend=True,              # Adds a color scale for the poverty rate
    legend_kwds={
        'label': 'Poverty Rate (0.0 to 1.0)', 
        'orientation': 'vertical',
        'shrink': 0.6         # Shrinks the color bar slightly so it doesn't dominate the map
    },
    ax=ax                     
)

# --- LAYER 2: THE POINTS (Grocery Stores) ---
# We map the colors to our 'price_tier' column
color_map = {
    '1 - Affordable (<$10)': 'green',
    '2 - Moderate ($10-$15)': 'orange',
    '3 - Expensive (>$15)': 'red'
}

# Plot each category one by one so we get a nice legend
for category, color in color_map.items():
    # Filter the stores to just this category
    subset = gdf_stores[gdf_stores['price_tier'] == category]
    
    # Plot this subset on top
    subset.plot(
        ax=ax,                    # TELLS PYTHON TO DRAW ON THE SAME CANVAS!
        color=color,
        markersize=50,            # Size of the dots
        edgecolor='black',        # Black outline around the dots
        linewidth=0.5,
        label=category            # The name for the legend
    )


# --- FINAL CLEANUP ---
plt.title('Atlanta Fresh Food Access: Store Affordability vs. Poverty', fontsize=16)
plt.axis('off') 

# Add the legend for the dots
# Add the legend for the grocery store dots
# Moved to 'upper left' to fill empty space, and added a shadow for readability against the blue
plt.legend(title="Store Basket Price", loc='upper left', frameon=True, shadow=True)

# Automatically adjust the plot to minimize wasted white space margins
plt.tight_layout()

# Save the map
output_image = 'atlanta_overlay_map_blue.png'
print(f"Saving stacked map to {output_image}...")
plt.savefig(output_image, dpi=300, bbox_inches='tight', facecolor='white')

# Show it
plt.show()