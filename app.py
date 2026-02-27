import json
import re
from math import asin, atan2, cos, degrees, radians, sin
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from shapely.geometry import shape
from shapely.ops import unary_union


st.set_page_config(
    page_title="Atlanta Food Providers Map",
    page_icon=":round_pushpin:",
    layout="wide",
)

CSV_PATH = Path("freshfoodproviders.csv")
FALLBACK_CSV_PATH = Path("food_providers_final_cleaned.csv")
BOUNDARY_PATH = Path("atlanta_city_limits.geojson")
MARTA_ROUTES_PATH = Path("marta_routes_overlay.geojson")
NETWORK_LAYER_DIR = Path("coverage_layers")
MAP_CENTER = {"lat": 33.7490, "lon": -84.3880}
EARTH_RADIUS_MI = 3958.7613
CIRCLE_STEPS = 48


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    return df.dropna(subset=["latitude", "longitude"]).copy()


@st.cache_data(show_spinner=False)
def load_boundary(path: Path):
    with path.open() as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_network_uncovered_layers(mode: str):
    layers = {}
    pattern = re.compile(rf"^{mode}_uncovered_(\d+(?:\.\d+)?)mi\.geojson$")
    if not NETWORK_LAYER_DIR.exists():
        return layers
    for path in NETWORK_LAYER_DIR.glob(f"{mode}_uncovered_*mi.geojson"):
        match = pattern.match(path.name)
        if not match:
            continue
        distance = round(float(match.group(1)), 1)
        layers[distance] = load_boundary(path)
    return layers


def extract_geometry(geojson_obj):
    if geojson_obj.get("type") == "FeatureCollection":
        return shape(geojson_obj["features"][0]["geometry"])
    if geojson_obj.get("type") == "Feature":
        return shape(geojson_obj["geometry"])
    return shape(geojson_obj)


def normalize_bool_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )


def destination_point(lat, lon, bearing_deg, distance_mi):
    angular_distance = distance_mi / EARTH_RADIUS_MI
    lat1 = radians(lat)
    lon1 = radians(lon)
    bearing = radians(bearing_deg)

    lat2 = asin(
        sin(lat1) * cos(angular_distance)
        + cos(lat1) * sin(angular_distance) * cos(bearing)
    )
    lon2 = lon1 + atan2(
        sin(bearing) * sin(angular_distance) * cos(lat1),
        cos(angular_distance) - sin(lat1) * sin(lat2),
    )
    return [degrees(lon2), degrees(lat2)]


def build_circle_feature(lat, lon, radius_mi):
    ring = [
        destination_point(lat, lon, (360 * step) / CIRCLE_STEPS, radius_mi)
        for step in range(CIRCLE_STEPS)
    ]
    ring.append(ring[0])
    return {
        "type": "Feature",
        "properties": {"radius_miles": radius_mi},
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


@st.cache_data(show_spinner=False)
def build_coverage_layers(boundary_geojson, points_records, radius_miles):
    boundary_geom = extract_geometry(boundary_geojson)
    circle_features = []
    circle_geoms = []

    for record in points_records:
        circle_feature = build_circle_feature(
            record["latitude"], record["longitude"], radius_miles
        )
        circle_features.append(circle_feature)
        circle_geoms.append(shape(circle_feature["geometry"]))

    coverage_geom = unary_union(circle_geoms) if circle_geoms else None
    uncovered_geom = (
        boundary_geom.difference(coverage_geom)
        if coverage_geom is not None
        else boundary_geom
    )

    return {
        "circle_outlines": {
            "type": "FeatureCollection",
            "features": circle_features,
        },
        "uncovered_mask": json.loads(json.dumps(uncovered_geom.__geo_interface__)),
    }


st.title("Atlanta Food Providers")
st.caption("Interactive map and table from `freshfoodproviders.csv`.")

if not CSV_PATH.exists() and not FALLBACK_CSV_PATH.exists():
    st.error(
        f"Could not find `{CSV_PATH}` or fallback `{FALLBACK_CSV_PATH}` in the app folder."
    )
    st.stop()

data_path = CSV_PATH if CSV_PATH.exists() else FALLBACK_CSV_PATH
df = load_data(data_path)
atlanta_boundary = load_boundary(BOUNDARY_PATH) if BOUNDARY_PATH.exists() else None
marta_routes = load_boundary(MARTA_ROUTES_PATH) if MARTA_ROUTES_PATH.exists() else None
walk_uncovered_layers = load_network_uncovered_layers("walk")
drive_uncovered_layers = load_network_uncovered_layers("drive")

with st.sidebar:
    st.header("Filters")
    search_text = st.text_input("Search company/DBA", "")

    coverage_distance_miles = st.slider(
        "Coverage distance (miles)", min_value=0.1, max_value=1.0, value=0.5, step=0.1
    )
    coverage_options = ["Euclidean"]
    if walk_uncovered_layers:
        coverage_options.append("Walk network")
    if drive_uncovered_layers:
        coverage_options.append("Drive network")
    coverage_mode = st.radio("Coverage model", coverage_options, index=0)

    district_values = sorted(df["council_district"].dropna().unique().tolist())
    selected_districts = st.multiselect(
        "Council district", district_values, default=district_values
    )

    npu_values = sorted(df["npu"].dropna().unique().tolist())
    selected_npus = st.multiselect("NPU", npu_values, default=npu_values)

    disinvested_series = normalize_bool_series(df["disinvested_neighborhood"])
    disinvested_options = ["All", "Disinvested only", "Not disinvested only"]
    disinvested_filter = st.selectbox(
        "Disinvested neighborhood", disinvested_options, index=0
    )

    marker_size = st.slider("Marker size", min_value=5, max_value=18, value=9)
    show_food_desert_mask = st.checkbox("Show coverage mask", value=True)
    show_marta_routes = st.checkbox(
        "Show MARTA routes",
        value=marta_routes is not None,
        disabled=marta_routes is None,
    )

filtered = df.copy()
filtered = filtered[filtered["council_district"].isin(selected_districts)]
filtered = filtered[filtered["npu"].isin(selected_npus)]

if disinvested_filter == "Disinvested only":
    filtered = filtered[disinvested_series.reindex(filtered.index) == True]
elif disinvested_filter == "Not disinvested only":
    filtered = filtered[disinvested_series.reindex(filtered.index) == False]

if search_text:
    pattern = search_text.strip().lower()
    mask = (
        filtered["company_name"].fillna("").str.lower().str.contains(pattern)
        | filtered["company_dba"].fillna("").str.lower().str.contains(pattern)
        | filtered["address_api"].fillna("").str.lower().str.contains(pattern)
    )
    filtered = filtered[mask]

st.subheader("Map")
st.write(f"Showing **{len(filtered):,}** of **{len(df):,}** providers.")
coverage_layers = None
network_uncovered = None
selected_distance = round(coverage_distance_miles, 1)
if coverage_mode == "Walk network":
    network_uncovered = walk_uncovered_layers.get(selected_distance)
elif coverage_mode == "Drive network":
    network_uncovered = drive_uncovered_layers.get(selected_distance)

if (
    show_food_desert_mask
    and atlanta_boundary is not None
    and coverage_mode == "Euclidean"
):
    coverage_layers = build_coverage_layers(
        atlanta_boundary,
        filtered[["latitude", "longitude"]].to_dict("records"),
        selected_distance,
    )
    st.caption(
        f"Shaded Atlanta areas fall outside the current {selected_distance:.1f}-mile provider coverage circles."
    )
elif show_food_desert_mask and network_uncovered is not None:
    st.caption(
        f"Shaded Atlanta areas fall outside the current {selected_distance:.1f}-mile {coverage_mode.lower()} provider coverage."
    )
elif show_food_desert_mask and coverage_mode != "Euclidean":
    st.caption(
        f"No precomputed {coverage_mode.lower()} layer for {selected_distance:.1f} miles yet. Run the precompute script to generate it."
    )
if show_marta_routes and marta_routes is not None:
    st.caption(
        "MARTA route lines are shown as a transit-access overlay. They are a useful proxy, not a full food-desert measure by themselves."
    )

fig = px.scatter_mapbox(
    filtered,
    lat="latitude",
    lon="longitude",
    hover_name="company_name",
    hover_data={
        "company_dba": True,
        "license_classification": True,
        "naics_name": True,
        "address_api": True,
        "latitude": ":.5f",
        "longitude": ":.5f",
    },
    zoom=11,
    height=680,
)
fig.update_layout(
    mapbox_style="open-street-map",
    mapbox_center=MAP_CENTER,
    margin={"l": 0, "r": 0, "t": 0, "b": 0},
    dragmode="pan",
)
map_layers = []
if coverage_layers is not None:
    map_layers.extend(
        [
            {
                "source": coverage_layers["uncovered_mask"],
                "sourcetype": "geojson",
                "type": "fill",
                "color": "#111827",
                "opacity": 0.28,
                "below": "traces",
            },
            {
                "source": coverage_layers["circle_outlines"],
                "sourcetype": "geojson",
                "type": "line",
                "color": "#FFE08A",
                "line": {"width": 1.5},
                "opacity": 0.6,
                "below": "traces",
            },
        ]
    )
elif show_food_desert_mask and network_uncovered is not None:
    map_layers.append(
        {
            "source": network_uncovered,
            "sourcetype": "geojson",
            "type": "fill",
            "color": "#111827",
            "opacity": 0.28,
            "below": "traces",
        }
    )
if show_marta_routes and marta_routes is not None:
    map_layers.append(
        {
            "source": marta_routes,
            "sourcetype": "geojson",
            "type": "line",
            "color": "#0B6E99",
            "line": {"width": 1.5},
            "opacity": 0.55,
            "below": "traces",
        }
    )
if atlanta_boundary is not None:
    map_layers.append(
        {
            "source": atlanta_boundary,
            "sourcetype": "geojson",
            "type": "line",
            "color": "#DB4437",
            "line": {"width": 3},
        }
    )
if map_layers:
    fig.update_layout(mapbox_layers=map_layers)
fig.update_traces(marker={"size": marker_size, "opacity": 0.75})
st.plotly_chart(
    fig,
    width="stretch",
    config={"scrollZoom": True, "displaylogo": False},
)

st.subheader("Provider table")
sort_columns = [
    "company_name",
    "company_dba",
    "council_district",
    "npu",
    "naics_name",
]
sort_col = st.selectbox("Sort by", sort_columns, index=0)
sort_ascending = st.checkbox("Ascending", value=True)
display_cols = [
    "license_number",
    "company_name",
    "company_dba",
    "license_classification",
    "naics_name",
    "address_api",
    "council_district",
    "npu",
    "disinvested_neighborhood",
    "latitude",
    "longitude",
]
table = filtered.sort_values(by=sort_col, ascending=sort_ascending)[display_cols]
st.dataframe(table, width="stretch", hide_index=True)
