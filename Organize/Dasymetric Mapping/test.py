import geopandas as gpd
gdf = gpd.read_file(r'D:\LZY\Projects\investAtlanta26\Organize\Dasymetric Mapping\Tax_Parcels_2025.shp')
print(gdf.columns.tolist())
print(gdf.head(3))