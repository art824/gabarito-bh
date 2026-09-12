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
        SELECT NULOTCTM, ID_QUADRA_CTM, AREA_M2, ID_LT, ST_AsWKB(geom) AS wkb,
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
    nulotctm, id_quadra, area_m2, id_lt, geom_wkb, dist = row
    return {
        "row": {"NULOTCTM": nulotctm, "ID_QUADRA_CTM": id_quadra, "AREA_M2": area_m2, "ID_LT": id_lt},
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
        "SELECT NULOTCTM, ID_QUADRA_CTM, AREA_M2, ID_LT, ST_AsWKB(geom) AS wkb "
        "FROM lotes WHERE NULOTCTM = ? LIMIT 1",
        [nulotctm],
    ).fetchone()
    if row is None:
        return None
    nulotctm_, id_quadra, area_m2, id_lt, geom_wkb = row
    return {
        "row": {"NULOTCTM": nulotctm_, "ID_QUADRA_CTM": id_quadra, "AREA_M2": area_m2, "ID_LT": id_lt},
        "poly": _wkb.loads(bytes(geom_wkb)),
    }


def edificacoes_por_lote(caminho_parquet, id_lt):
    """Construções do levantamento aéreo de 2015 (EDIFICACAO) de um lote, pela
    chave ID_LT do CTM (o join por essa chave bate em 99,4% das construções).
    Lê direto do Parquet, que está ORDENADO por ID_LT: só o pedaço do arquivo
    com esse lote é lido, nada fica na RAM. Lista vazia se o arquivo não
    existir ou se o lote não tiver construção registrada no voo."""
    if not caminho_parquet or id_lt is None:
        return []
    con = duckdb.connect()
    try:
        linhas = con.execute(
            f"SELECT area_m2, altura_m, obs, wkb FROM read_parquet('{Path(caminho_parquet).as_posix()}') "
            "WHERE ID_LT = ?",
            [int(id_lt)],
        ).fetchall()
    finally:
        con.close()
    return [{"area_m2": float(a), "altura_m": float(h), "obs": int(o), "poly": _wkb.loads(bytes(w))}
            for a, h, o, w in linhas]


def projetos_por_nulotctm(caminho_parquet, nulotctm):
    """Projetos de edificação APROVADOS na Prefeitura cujo terreno cai nesse
    lote (o join espacial é feito uma vez só, no preparar_dados). Mais recente
    primeiro. Lista vazia se o arquivo não existir."""
    if not caminho_parquet or not nulotctm:
        return []
    con = duckdb.connect()
    try:
        cur = con.execute(
            f"SELECT * FROM read_parquet('{Path(caminho_parquet).as_posix()}') WHERE NULOTCTM = ?",
            [str(nulotctm)],
        )
        colunas = [d[0] for d in cur.description]
        linhas = [dict(zip(colunas, r)) for r in cur.fetchall()]
    finally:
        con.close()
    linhas.sort(key=lambda r: str(r.get("dt_aprovacao") or ""), reverse=True)
    return linhas
