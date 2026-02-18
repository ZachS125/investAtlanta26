# Atlanta Food Providers Map

Streamlit + Plotly app that maps all provider locations from `food_providers_final_cleaned.csv` using latitude/longitude.

## Files used

- `app.py`
- `food_providers_final_cleaned.csv`
- `requirements.txt`

## Run locally (venv)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

App URL: `http://localhost:8501`

## Run on local network (share with same Wi-Fi)

```bash
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8502
```

Then open from another device with:

`http://<your-mac-local-ip>:8502`

Example:

`http://10.44.255.5:8502`

## Deploy on Streamlit Community Cloud (easiest)

1. Push this repo to GitHub.
2. Go to [https://share.streamlit.io](https://share.streamlit.io).
3. Click **New app**.
4. Select repo: `ZachS125/investAtlanta26`.
5. Set main file path: `app.py`.
6. Click **Deploy**.

Notes:
- `requirements.txt` is auto-detected and installed.
- Keep `food_providers_final_cleaned.csv` in repo root so the app can read it.

## Deploy on Render

1. Create a **Web Service** from this GitHub repo.
2. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
3. Deploy.

## Troubleshooting

- `streamlit: command not found`
  - Use: `.venv/bin/python -m streamlit run app.py`
- Blank map or no points
  - Confirm `food_providers_final_cleaned.csv` exists in repo root.
  - Confirm `latitude` and `longitude` columns are present and numeric.
