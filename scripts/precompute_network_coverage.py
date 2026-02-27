import argparse
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
from shapely.geometry import shape
from shapely.ops import unary_union

MILES_TO_METERS = 1609.344
DEFAULT_DISTANCE_START = 0.1
DEFAULT_DISTANCE_END = 1.0
DEFAULT_DISTANCE_STEP = 0.1
ATLANTA_CRS = "EPSG:4326"
NETWORK_CONFIG = {
    "walk": {"edge_buffer_m": 60, "node_buffer_m": 40},
    "drive": {"edge_buffer_m": 90, "node_buffer_m": 60},
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Precompute walk/drive network coverage masks for Atlanta providers."
    )
    parser.add_argument(
        "--csv",
        default="freshfoodproviders.csv",
        help="Provider CSV with latitude/longitude columns.",
    )
    parser.add_argument(
        "--boundary",
        default="atlanta_city_limits.geojson",
        help="Atlanta boundary GeoJSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="coverage_layers",
        help="Directory for GeoJSON outputs.",
    )
    parser.add_argument(
        "--distance-miles",
        type=float,
        help="Single network travel distance in miles (overrides range flags).",
    )
    parser.add_argument(
        "--distance-start",
        type=float,
        default=DEFAULT_DISTANCE_START,
        help="Distance range start (miles).",
    )
    parser.add_argument(
        "--distance-end",
        type=float,
        default=DEFAULT_DISTANCE_END,
        help="Distance range end (miles).",
    )
    parser.add_argument(
        "--distance-step",
        type=float,
        default=DEFAULT_DISTANCE_STEP,
        help="Distance range increment (miles).",
    )
    parser.add_argument(
        "--distances",
        default="",
        help="Comma-separated distance list in miles, e.g. 0.1,0.3,0.7.",
    )
    parser.add_argument(
        "--modes",
        default="walk,drive",
        help="Comma-separated network modes to compute: walk, drive.",
    )
    return parser.parse_args()


def load_boundary_geometry(path: Path):
    with path.open() as f:
        geojson_obj = json.load(f)
    if geojson_obj.get("type") == "FeatureCollection":
        return shape(geojson_obj["features"][0]["geometry"])
    if geojson_obj.get("type") == "Feature":
        return shape(geojson_obj["geometry"])
    return shape(geojson_obj)


def load_provider_points(path: Path):
    df = pd.read_csv(path)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    return gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs=ATLANTA_CRS,
    )


def build_service_area(graph_proj, origin_nodes, distance_m, edge_buffer_m, node_buffer_m):
    coverage_polygons = []

    for idx, node_id in enumerate(sorted(set(origin_nodes)), start=1):
        subgraph = nx.ego_graph(
            graph_proj, node_id, radius=distance_m, distance="length"
        )
        geoms = []
        if subgraph.number_of_nodes() > 0:
            nodes_gdf = ox.graph_to_gdfs(subgraph, nodes=True, edges=False)
            if not nodes_gdf.empty:
                geoms.extend(nodes_gdf.geometry.buffer(node_buffer_m).tolist())
        if subgraph.number_of_edges() > 0:
            edges_gdf = ox.graph_to_gdfs(
                subgraph, nodes=False, edges=True, fill_edge_geometry=True
            )
            if not edges_gdf.empty:
                geoms.extend(edges_gdf.geometry.buffer(edge_buffer_m).tolist())
        if geoms:
            coverage_polygons.append(unary_union(geoms).convex_hull)

        if idx % 25 == 0 or idx == len(set(origin_nodes)):
            print(f"  processed {idx}/{len(set(origin_nodes))} origin nodes")

    return unary_union(coverage_polygons) if coverage_polygons else None


def save_geometry(geometry, crs, path: Path):
    gdf = gpd.GeoDataFrame({"name": [path.stem]}, geometry=[geometry], crs=crs)
    gdf.to_crs(ATLANTA_CRS).to_file(path, driver="GeoJSON")


def parse_distances(args):
    if args.distance_miles is not None:
        return [round(args.distance_miles, 1)]
    if args.distances.strip():
        values = [round(float(v.strip()), 1) for v in args.distances.split(",") if v.strip()]
        return sorted(set(values))

    distances = []
    current = args.distance_start
    while current <= args.distance_end + 1e-9:
        distances.append(round(current, 1))
        current += args.distance_step
    return sorted(set(distances))


def parse_modes(args):
    requested = [m.strip().lower() for m in args.modes.split(",") if m.strip()]
    invalid = [m for m in requested if m not in NETWORK_CONFIG]
    if invalid:
        raise ValueError(f"Unsupported mode(s): {', '.join(invalid)}")
    return requested or list(NETWORK_CONFIG.keys())


def main():
    args = parse_args()
    csv_path = Path(args.csv)
    boundary_path = Path(args.boundary)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    boundary_geom = load_boundary_geometry(boundary_path)
    boundary_gdf = gpd.GeoDataFrame({"name": ["atlanta"]}, geometry=[boundary_geom], crs=ATLANTA_CRS)
    providers_gdf = load_provider_points(csv_path)
    distances = parse_distances(args)
    modes = parse_modes(args)

    summary = {
        "distances_miles": distances,
        "provider_count": int(len(providers_gdf)),
        "modes": {mode: {} for mode in modes},
    }

    for mode in modes:
        config = NETWORK_CONFIG[mode]
        print(f"Building {mode} network...")
        graph = ox.graph_from_polygon(
            boundary_geom,
            network_type=mode,
            simplify=True,
            retain_all=False,
            truncate_by_edge=True,
        )
        graph_proj = ox.project_graph(graph)
        graph_crs = graph_proj.graph["crs"]

        boundary_proj = boundary_gdf.to_crs(graph_crs).geometry.iloc[0]
        providers_proj = providers_gdf.to_crs(graph_crs)
        origin_nodes = ox.distance.nearest_nodes(
            graph_proj,
            X=providers_proj.geometry.x.tolist(),
            Y=providers_proj.geometry.y.tolist(),
        )

        for distance_miles in distances:
            print(f"Computing {mode} service area polygons for {distance_miles:.1f} miles...")
            coverage_geom = build_service_area(
                graph_proj,
                origin_nodes,
                distance_miles * MILES_TO_METERS,
                config["edge_buffer_m"],
                config["node_buffer_m"],
            )
            coverage_geom = coverage_geom.intersection(boundary_proj)
            uncovered_geom = boundary_proj.difference(coverage_geom)

            coverage_path = output_dir / f"{mode}_coverage_{distance_miles:.1f}mi.geojson"
            uncovered_path = output_dir / f"{mode}_uncovered_{distance_miles:.1f}mi.geojson"
            save_geometry(coverage_geom, graph_crs, coverage_path)
            save_geometry(uncovered_geom, graph_crs, uncovered_path)

            total_area = boundary_proj.area
            covered_area = coverage_geom.area
            summary["modes"][mode][f"{distance_miles:.1f}"] = {
                "coverage_path": str(coverage_path),
                "uncovered_path": str(uncovered_path),
                "unique_origin_nodes": int(len(set(origin_nodes))),
                "covered_area_sq_m": float(covered_area),
                "uncovered_area_sq_m": float(uncovered_geom.area),
                "coverage_ratio": float(covered_area / total_area) if total_area else 0.0,
            }

    summary_path = output_dir / "network_coverage_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    main()
