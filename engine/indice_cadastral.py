# -*- coding: utf-8 -*-
"""
Busca de lote por Índice Cadastral do IPTU (sem geocodificação de endereço).
Usa data/geo/_cache/INDICE_CADASTRAL.parquet (índice -> NULOTCTM + dados do
cadastro imobiliário) e o LOTE_CTM (geometria real do lote) pra achar o
centróide e alimentar o mesmo `consultar()` usado na busca por endereço.
"""
import re

import geopandas as gpd


class IndiceCadastralError(Exception):
    pass


def _normalizar(indice: str) -> str:
    return re.sub(r"\s+", "", indice or "").upper()


def buscar_por_indice(indice: str, df_indice, lote_ctm) -> dict:
    if df_indice is None:
        raise IndiceCadastralError(
            "Base de índice cadastral não carregada (rode scripts/preparar_dados.py)."
        )
    if lote_ctm is None:
        raise IndiceCadastralError("Base de lotes (CTM) não carregada.")

    alvo = _normalizar(indice)
    if not alvo:
        raise IndiceCadastralError("Informe um índice cadastral.")

    normalizados = df_indice["INDICE_CADASTRAL"].str.replace(r"\s+", "", regex=True).str.upper()
    hit = df_indice[normalizados == alvo]
    if hit.empty:
        raise IndiceCadastralError(
            f"Índice cadastral '{indice}' não encontrado na base do IPTU."
        )
    registro = hit.iloc[0]
    nulotctm = registro["NULOTCTM"]

    lote_hit = lote_ctm[lote_ctm["NULOTCTM"] == nulotctm]
    if lote_hit.empty:
        raise IndiceCadastralError(
            f"Índice '{indice}' encontrado, mas sem lote correspondente na base CTM (NULOTCTM {nulotctm})."
        )
    poly = lote_hit.iloc[0].geometry
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
