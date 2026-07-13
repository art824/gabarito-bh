# -*- coding: utf-8 -*-
"""
Consulta indexada em disco pro LOTE_CTM e pro INDICE_CADASTRAL (IPTU), via
DuckDB + extensão espacial (RTREE). Troca o antigo "carrega TODO lote de BH
na memória e faz .distance() no GeoDataFrame inteiro" (~562MB de RAM só pro
LOTE_CTM) por uma consulta pontual no arquivo em disco (~100-150MB de RAM
total, resposta em <100ms depois do primeiro warmup).

Os bancos (.duckdb) são gerados por scripts/preparar_dados.py a partir dos
mesmos Parquet/GeoParquet já existentes — rodar esse script de novo depois
de baixar CSV novo do BHMAP.
"""
from pathlib import Path

import duckdb
from shapely import wkb as _wkb

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "data" / "geo" / "_cache"
DB_LOTES = CACHE / "lotes.duckdb"
DB_INDICE = CACHE / "indice_cadastral.duckdb"


def conectar_lotes():
    """Conexão read-only pro banco de lotes CTM (com índice espacial). None
    se o banco ainda não foi gerado (preparar_dados.py não rodou)."""
    if not DB_LOTES.exists():
        return None
    con = duckdb.connect(str(DB_LOTES), read_only=True)
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


def conectar_indice():
    """Conexão read-only pro banco do cadastro imobiliário (IPTU)."""
    if not DB_INDICE.exists():
        return None
    return duckdb.connect(str(DB_INDICE), read_only=True)


def lote_mais_proximo(con, x: float, y: float, limiar_m: float):
    """Lote CTM mais próximo do ponto (x,y em EPSG:31983), usando o índice
    RTREE — só varre lotes dentro do limiar, não a tabela inteira. None se
    não achar nada dentro do limiar."""
    if con is None:
        return None
    row = con.execute(
        """
        SELECT NULOTCTM, ID_QUADRA_CTM, AREA_M2, ST_AsWKB(geom) AS wkb,
               ST_Distance(geom, ST_Point(?, ?)) AS dist
        FROM lotes
        WHERE ST_DWithin(geom, ST_Point(?, ?), ?)
        ORDER BY dist
        LIMIT 1
        """,
        [x, y, x, y, limiar_m],
    ).fetchone()
    if row is None:
        return None
    nulotctm, id_quadra, area_m2, geom_wkb, dist = row
    return {
        "row": {"NULOTCTM": nulotctm, "ID_QUADRA_CTM": id_quadra, "AREA_M2": area_m2},
        "poly": _wkb.loads(bytes(geom_wkb)),
        "distancia_m": round(float(dist), 1),
    }


def registros_indice_por_nulotctm(con, nulotctm: str):
    """Todos os registros do cadastro imobiliário (uma linha por 'economia')
    com esse NULOTCTM. Lista vazia se não achar ou banco não existir."""
    if con is None or not nulotctm:
        return []
    cur = con.execute("SELECT * FROM indice WHERE NULOTCTM = ?", [nulotctm])
    colunas = [d[0] for d in cur.description]
    return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def registro_por_indice_cadastral(con, indice_normalizado: str):
    """Um registro do cadastro imobiliário pelo índice cadastral do IPTU
    (já normalizado: sem espaço, maiúsculo). None se não achar."""
    if con is None or not indice_normalizado:
        return None
    cur = con.execute(
        "SELECT * FROM indice WHERE upper(regexp_replace(INDICE_CADASTRAL, '\\s+', '', 'g')) = ? LIMIT 1",
        [indice_normalizado],
    )
    colunas = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(colunas, row)) if row else None


def lote_por_nulotctm(con, nulotctm: str):
    """Lote CTM com esse NULOTCTM exato (não é busca espacial — chave direta).
    Mesmo formato de retorno que lote_mais_proximo, sem 'distancia_m'."""
    if con is None or not nulotctm:
        return None
    row = con.execute(
        "SELECT NULOTCTM, ID_QUADRA_CTM, AREA_M2, ST_AsWKB(geom) AS wkb "
        "FROM lotes WHERE NULOTCTM = ? LIMIT 1",
        [nulotctm],
    ).fetchone()
    if row is None:
        return None
    nulotctm_, id_quadra, area_m2, geom_wkb = row
    return {
        "row": {"NULOTCTM": nulotctm_, "ID_QUADRA_CTM": id_quadra, "AREA_M2": area_m2},
        "poly": _wkb.loads(bytes(geom_wkb)),
    }
