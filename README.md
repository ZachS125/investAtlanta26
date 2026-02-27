# Atlanta Food Providers Map

Interactive Streamlit + Plotly map for Atlanta food providers with food-access coverage views.

## What this app does

- Plots providers from `freshfoodproviders.csv` (lat/lon)
- Shows a clear Atlanta city boundary
- Optional MARTA routes overlay
- Food-access masking with selectable distance and model:
  - Euclidean distance
  - Walk-network distance (precomputed)
  - Drive-network distance (precomputed)
- Distance selector from `0.1` to `1.0` miles in `0.1` increments

## Core files

- `app.py`
- `freshfoodproviders.csv`
- `atlanta_city_limits.geojson`
- `marta_routes_overlay.geojson`
- `coverage_layers/` (precomputed walk/drive coverage GeoJSONs)
- `requirements.txt`
- `requirements-precompute.txt`
- `scripts/precompute_network_coverage.py`

## Run locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## Run on local network

```bash
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8502
```

Open from another device on the same network:

`http://<your-local-ip>:8502`

## Precompute network coverage layers (walk + drive)

Use this when provider data changes or you want refreshed network coverage masks.

Install precompute dependencies:

```bash
.venv/bin/python -m pip install -r requirements-precompute.txt
```

Generate all distances (`0.1` to `1.0`) for both walk and drive:

```bash
.venv/bin/python scripts/precompute_network_coverage.py
```

Useful optional runs:

```bash
# only drive mode
.venv/bin/python scripts/precompute_network_coverage.py --modes drive

# single distance only
.venv/bin/python scripts/precompute_network_coverage.py --distance-miles 0.5

# custom list
.venv/bin/python scripts/precompute_network_coverage.py --distances 0.2,0.4,0.8
```

Outputs are written to `coverage_layers/`.

## Deploy (Streamlit Community Cloud)

1. Push repo to GitHub.
2. Go to [https://share.streamlit.io](https://share.streamlit.io).
3. Create a new app pointing to `app.py`.
4. Ensure required data files remain in repo root (`freshfoodproviders.csv`, boundary/routes GeoJSON, `coverage_layers/`).

## Notes

- Network mode layers are precomputed from OpenStreetMap roads (via OSMnx).
- Euclidean mode is computed on the fly in the app.
- If a network layer for a selected distance is missing, the app will show a message prompting precompute.
