# -*- coding: utf-8 -*-
"""
Geocodificação endereço -> lat/lon via Mapbox Geocoding API v6.
Restrito à bbox de Belo Horizonte para evitar resultados fora da cidade.

Uso:
    python geocode.py "Praça da Liberdade, Belo Horizonte"
"""
import os
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MAPBOX_TOKEN = os.environ.get("MAPBOX_TOKEN")

# bbox aproximado de BH (min_lon, min_lat, max_lon, max_lat)
BH_BBOX = "-44.10,-20.05,-43.85,-19.75"

URL = "https://api.mapbox.com/search/geocode/v6/forward"


class GeocodeError(Exception):
    pass


def endereco_para_latlon(endereco: str) -> dict:
    if not MAPBOX_TOKEN:
        raise GeocodeError("MAPBOX_TOKEN não configurado (esperado em .env na raiz do projeto).")

    params = {
        "q": f"{endereco}, Belo Horizonte, MG",
        "access_token": MAPBOX_TOKEN,
        "country": "br",
        "bbox": BH_BBOX,
        "limit": 1,
        "language": "pt",
    }
    resp = requests.get(URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    features = data.get("features", [])
    if not features:
        raise GeocodeError(f"Endereço não encontrado em BH: '{endereco}'")

    f = features[0]
    lon, lat = f["geometry"]["coordinates"]
    return {
        "lat": lat,
        "lon": lon,
        "nome_encontrado": f["properties"].get("full_address") or f["properties"].get("name"),
        "tipo": f["properties"].get("feature_type"),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python geocode.py \"<endereço>\"")
        sys.exit(1)
    endereco = " ".join(sys.argv[1:])
    try:
        r = endereco_para_latlon(endereco)
        print(f"Encontrado: {r['nome_encontrado']}")
        print(f"lat={r['lat']}, lon={r['lon']} (tipo: {r['tipo']})")
    except GeocodeError as e:
        print(f"ERRO: {e}")
        sys.exit(1)
