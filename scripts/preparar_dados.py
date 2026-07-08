# -*- coding: utf-8 -*-
"""
Converte os CSVs grandes do BHMAP (WKT em EPSG:31983) para Parquet/GeoParquet
em data/geo/_cache/, pra não reparsear centenas de MB de texto toda vez que
o servidor sobe.

Rodar manualmente sempre que um CSV novo/atualizado chegar em data/geo/:
    python scripts/preparar_dados.py
"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import geopandas as gpd

BASE = Path(__file__).resolve().parent.parent
GEO = BASE / "data" / "geo"
CACHE = GEO / "_cache"
CRS = "EPSG:31983"


def geo_parquet(csv_nome: str, saida_nome: str, colunas: list[str] | None = None,
                 dtype: dict | None = None):
    origem = GEO / csv_nome
    if not origem.exists():
        print(f"  PULADO — {csv_nome} não encontrado em data/geo/")
        return
    t0 = time.time()
    df = pd.read_csv(origem, usecols=colunas, dtype=dtype)
    geom = gpd.GeoSeries.from_wkt(df["GEOMETRIA"])
    gdf = gpd.GeoDataFrame(df.drop(columns=["GEOMETRIA"]), geometry=geom, crs=CRS)
    destino = CACHE / saida_nome
    gdf.to_parquet(destino)
    print(f"  {csv_nome} -> {saida_nome}: {len(gdf)} linhas em {time.time()-t0:.1f}s")


def indice_cadastral_parquet():
    origem = GEO / "CADASTRO_IMOBILIARIO.csv"
    if not origem.exists():
        print("  PULADO — CADASTRO_IMOBILIARIO.csv não encontrado em data/geo/")
        return
    t0 = time.time()
    colunas = [
        "INDICE_CADASTRAL", "NULOTCTM", "TIPO_LOGRADOURO", "NOME_LOGRADOURO",
        "NUMERO_IMOVEL", "CEP", "COMPLEMENTO_ENDERECO", "AREA_TERRENO",
        "AREA_CONSTRUCAO", "TIPO_CONSTRUTIVO", "TIPO_OCUPACAO",
        "PADRAO_ACABAMENTO", "QUANTIDADE_ECONOMIAS", "ANO_CONSTRUCAO",
        "IND_MEIO_FIO", "IND_PAVIMENTACAO", "IND_ARBORIZACAO",
        "IND_GALERIA_PLUVIAL", "IND_ILUMINACAO_PUBLICA", "IND_REDE_ESGOTO",
        "IND_REDE_AGUA", "IND_REDE_TELEFONICA",
    ]
    df = pd.read_csv(origem, usecols=colunas, dtype=str)
    destino = CACHE / "INDICE_CADASTRAL.parquet"
    df.to_parquet(destino)
    print(f"  CADASTRO_IMOBILIARIO.csv -> INDICE_CADASTRAL.parquet: "
          f"{len(df)} linhas em {time.time()-t0:.1f}s")


if __name__ == "__main__":
    CACHE.mkdir(parents=True, exist_ok=True)
    print("Preparando camadas (Parquet/GeoParquet)...")
    # NULOTCTM tem zeros à esquerda (chave de junção com o índice cadastral do
    # IPTU) — precisa ler como texto, senão vira int e perde os zeros.
    geo_parquet("LOTE_CTM.csv", "LOTE_CTM.parquet", dtype={"NULOTCTM": str})
    geo_parquet("CENTRALIDADE_LOCAL_11181.csv", "CENTRALIDADE_LOCAL.parquet")
    geo_parquet("RECUO_ALINHAMENTO_11181.csv", "RECUO_ALINHAMENTO.parquet")
    geo_parquet("ADE_SETORES_11181.csv", "ADE_SETORES.parquet")
    geo_parquet("BAIRRO_OFICIAL.csv", "BAIRRO_OFICIAL.parquet")
    geo_parquet("BAIRRO_POPULAR.csv", "BAIRRO_POPULAR.parquet")
    geo_parquet("PROJ_VIARIO_PRIOR_11181.csv", "PROJ_VIARIO_PRIOR.parquet")
    indice_cadastral_parquet()
    print("Concluído.")
