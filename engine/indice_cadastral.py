# -*- coding: utf-8 -*-
"""
Busca de lote por Índice Cadastral do IPTU (sem geocodificação de endereço).
Consulta direto os bancos DuckDB indexados (data/geo/_cache/*.duckdb) em vez
de carregar INDICE_CADASTRAL/LOTE_CTM inteiros na memória — ver
engine/db_lotes.py.
"""
import re

import geopandas as gpd

from db_lotes import registro_por_indice_cadastral, lote_por_nulotctm


class IndiceCadastralError(Exception):
    pass


def _normalizar(indice: str) -> str:
    return re.sub(r"\s+", "", indice or "").upper()


def buscar_por_indice(indice: str, con_indice, con_lotes) -> dict:
    if con_indice is None:
        raise IndiceCadastralError(
            "Base de índice cadastral não carregada (rode scripts/preparar_dados.py)."
        )
    if con_lotes is None:
        raise IndiceCadastralError("Base de lotes (CTM) não carregada.")

    alvo = _normalizar(indice)
    if not alvo:
        raise IndiceCadastralError("Informe um índice cadastral.")

    registro = registro_por_indice_cadastral(con_indice, alvo)
    if registro is None:
        raise IndiceCadastralError(
            f"Índice cadastral '{indice}' não encontrado na base do IPTU."
        )
    nulotctm = registro["NULOTCTM"]

    achado = lote_por_nulotctm(con_lotes, nulotctm)
    if achado is None:
        raise IndiceCadastralError(
            f"Índice '{indice}' encontrado, mas sem lote correspondente na base CTM (NULOTCTM {nulotctm})."
        )
    poly = achado["poly"]
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    centro = poly.representative_point()  # sempre dentro do polígono (centroid pode cair fora em formas côncavas)

    centro_wgs = gpd.GeoSeries([centro], crs="EPSG:31983").to_crs("EPSG:4326").iloc[0]

    endereco_partes = [
        registro.get("TIPO_LOGRADOURO"), registro.get("NOME_LOGRADOURO"),
        str(registro.get("NUMERO_IMOVEL") or "").strip(),
    ]
    endereco = " ".join(p for p in endereco_partes if p and str(p).strip())

    return {
        "lat": centro_wgs.y,
        "lon": centro_wgs.x,
        "nome_encontrado": endereco or f"Índice cadastral {registro['INDICE_CADASTRAL']}",
        "nulotctm": nulotctm,
        "registro_iptu": registro,
    }
