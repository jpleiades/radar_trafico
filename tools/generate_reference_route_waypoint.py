import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ORIGIN = (40.406049, -3.7785792)
WAYPOINT = (40.46007679671718, -3.7704688756394287)
DESTINATION = (40.4893341, -3.6933343)
WAYPOINT_RADIUS_METERS = 20

ORIGIN_ADDRESS = "Calle Zaragoza, 11, 28223 Pozuelo de Alarcón, Madrid, España"
DESTINATION_ADDRESS = "Editorial Edelvives, Calle Xaudaró, 25, 28034 Madrid, España"


def main() -> None:
    api_key = os.environ.get("TOMTOM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Falta TOMTOM_API_KEY")

    output = Path(sys.argv[1] if len(sys.argv) > 1 else "state/reference_route.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    origin = f"{ORIGIN[0]},{ORIGIN[1]}"
    waypoint = f"circle({WAYPOINT[0]},{WAYPOINT[1]},{WAYPOINT_RADIUS_METERS})"
    destination = f"{DESTINATION[0]},{DESTINATION[1]}"
    locations = f"{origin}:{waypoint}:{destination}"

    url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"
    params = {
        "key": api_key,
        "traffic": "true",
        "travelMode": "car",
        "routeType": "fastest",
        "routeRepresentation": "encodedPolyline",
        "coordinatePrecision": "full",
        "computeTravelTimeFor": "all",
        "language": "es-ES",
        "maxAlternatives": 0,
    }

    print("Generando ruta fija pasando por el waypoint obligatorio...")
    response = requests.get(url, params=params, timeout=45)
    if not response.ok:
        raise RuntimeError(
            f"TomTom devolvió HTTP {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    routes = data.get("routes") or []
    if not routes:
        raise RuntimeError("TomTom no devolvió ninguna ruta")

    route = routes[0]
    legs = route.get("legs") or []
    if len(legs) != 1:
        raise RuntimeError(
            f"Se esperaba una sola etapa usando un circle waypoint y TomTom devolvió {len(legs)}"
        )

    leg = legs[0]
    encoded_polyline = leg.get("encodedPolyline")
    precision = leg.get("encodedPolylinePrecision")
    if not encoded_polyline or precision not in (5, 7):
        raise RuntimeError("TomTom no devolvió una polilínea codificada válida")

    summary = route.get("summary") or {}
    distance_meters = summary.get("lengthInMeters")
    if not distance_meters:
        raise RuntimeError("TomTom no devolvió la distancia de la ruta")

    reference = {
        "origin_address": ORIGIN_ADDRESS,
        "destination_address": DESTINATION_ADDRESS,
        "origin": {"lat": ORIGIN[0], "lon": ORIGIN[1]},
        "destination": {"lat": DESTINATION[0], "lon": DESTINATION[1]},
        "waypoint": {
            "lat": WAYPOINT[0],
            "lon": WAYPOINT[1],
            "radius_meters": WAYPOINT_RADIUS_METERS,
        },
        "encoded_polyline": encoded_polyline,
        "encoded_polyline_precision": precision,
        "distance_meters": int(distance_meters),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    output.write_text(
        json.dumps(reference, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(f"Ruta guardada en {output}")
    print(f"Distancia: {distance_meters / 1000:.2f} km")
    print(
        "Waypoint obligatorio: "
        f"{WAYPOINT[0]:.7f}, {WAYPOINT[1]:.7f} "
        f"(radio {WAYPOINT_RADIUS_METERS} m)"
    )


if __name__ == "__main__":
    main()
