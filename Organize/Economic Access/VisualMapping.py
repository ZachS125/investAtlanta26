import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

print("Loading Atlanta Census Data...")

# 1. Load the shapefile
gdf = gpd.read_file(r'D:\LZY\Projects\investAtlanta26\Organize\Economic Access\lila_halfmi_census.shp')

# 2. Clean the data column we want to map
gdf['PvrtyRt'] = pd.to_numeric(gdf['PvrtyRt'], errors='coerce')

# 3. Set up the "Canvas" for our map
fig, ax = plt.subplots(figsize=(12, 10))

# 4. DRAW THE MAP
print("Drawing the map...")
gdf.plot(
    column='PvrtyRt',         
    cmap='OrRd',              
    legend=True,              
    legend_kwds={'label': 'Poverty Rate', 'orientation': 'vertical'},
    edgecolor='black',        
    linewidth=0.2,            
    missing_kwds={'color': 'lightgrey'}, 
    ax=ax
)

# 5. Add a title and clean up the look
plt.title('Atlanta Census Tracts: Poverty Rate (LILA Data)', fontsize=16)
plt.axis('off') 

# ==========================================
# 6. SAVE THE MAP (NEW CODE)
# ==========================================
output_image = 'atlanta_poverty_map.png'
print(f"Saving high-resolution map to {output_image}...")

plt.savefig(
    output_image, 
    dpi=300,                # 300 DPI is standard print-quality resolution
    bbox_inches='tight',    # This automatically crops out extra white space around the edges
    facecolor='white'       # Ensures the background is white, not transparent
)

# 7. Show the map on your screen
print("Opening map viewer...")
plt.show()