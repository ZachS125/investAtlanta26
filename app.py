from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Atlanta Food Providers Map",
    page_icon=":round_pushpin:",
    layout="wide",
)

CSV_PATH = Path("food_providers_final_cleaned.csv")
MAP_CENTER = {"lat": 33.7490, "lon": -84.3880}


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    return df.dropna(subset=["latitude", "longitude"]).copy()


def normalize_bool_series(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False})
    )


st.title("Atlanta Food Providers")
st.caption("Interactive map and table from `food_providers_final_cleaned.csv`.")

if not CSV_PATH.exists():
    st.error(f"Could not find `{CSV_PATH}` in the app folder.")
    st.stop()

df = load_data(CSV_PATH)

with st.sidebar:
    st.header("Filters")
    search_text = st.text_input("Search company/DBA", "")

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

    zoom_level = st.slider("Initial zoom", min_value=8, max_value=16, value=11)
    marker_size = st.slider("Marker size", min_value=5, max_value=18, value=9)

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
    zoom=zoom_level,
    height=680,
)
fig.update_layout(
    mapbox_style="open-street-map",
    mapbox_center=MAP_CENTER,
    margin={"l": 0, "r": 0, "t": 0, "b": 0},
)
fig.update_traces(marker={"size": marker_size, "opacity": 0.75})
st.plotly_chart(fig, use_container_width=True)

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
st.dataframe(table, use_container_width=True, hide_index=True)
