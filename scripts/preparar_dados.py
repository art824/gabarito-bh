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
import duckdb

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


def _ler_dbf_latin1(caminho_dbf: Path) -> pd.DataFrame:
    """Lê os ATRIBUTOS de um .dbf decodificando em latin-1 na mão.

    Por que não usar geopandas/pyogrio: nesses shapefiles do BHMAP o byte 29
    do header do .dbf (LDID, "language driver id") é 0x00 — ou seja, o
    arquivo NÃO declara seu encoding. Nessa situação o GDAL ignora tanto o
    arquivo .cst irmão (que diz ISO-8859-1) quanto o parâmetro `encoding=`
    do read_file, e devolve os acentos como U+FFFD (caractere de
    substituição), o que é IRREVERSÍVEL depois de lido. Os bytes no disco
    estão corretos (`Per\\xedmetro` = latin-1 válido) — só precisam ser
    decodificados direto. Formato DBF3 é simples e estável, daí o parser.
    """
    import struct
    raw = caminho_dbf.read_bytes()
    n_registros = struct.unpack("<I", raw[4:8])[0]
    tam_header = struct.unpack("<H", raw[8:10])[0]
    tam_registro = struct.unpack("<H", raw[10:12])[0]

    campos, pos = [], 32
    while raw[pos] != 0x0D:  # 0x0D encerra a lista de descritores de campo
        nome = raw[pos:pos + 11].split(b"\x00")[0].decode("latin-1")
        tipo = chr(raw[pos + 11])
        tamanho = raw[pos + 16]
        campos.append((nome, tipo, tamanho))
        pos += 32

    linhas = []
    for i in range(n_registros):
        ini = tam_header + i * tam_registro
        registro = raw[ini:ini + tam_registro]
        if not registro:
            break
        valores, p = {}, 1  # byte 0 = flag de exclusão
        for nome, tipo, tamanho in campos:
            texto = registro[p:p + tamanho].decode("latin-1").strip()
            p += tamanho
            if tipo in "NF":
                valores[nome] = float(texto) if texto else None
            else:
                valores[nome] = texto or None
        linhas.append(valores)
    return pd.DataFrame(linhas)


def shp_parquet(pasta_nome: str, saida_nome: str):
    """Converte um shapefile do BHMAP para Parquet corrigindo o encoding dos
    atributos (ver _ler_dbf_latin1). A GEOMETRIA vem do geopandas (essa parte
    o GDAL lê certo); só os textos são relidos do .dbf."""
    origem = GEO / pasta_nome / f"{pasta_nome}.shp"
    if not origem.exists():
        print(f"  PULADO — {pasta_nome}.shp não encontrado em data/geo/{pasta_nome}/")
        return
    t0 = time.time()
    gdf = gpd.read_file(origem)
    atributos = _ler_dbf_latin1(origem.with_suffix(".dbf"))
    if len(atributos) == len(gdf):
        for coluna in atributos.columns:
            if coluna in gdf.columns:
                gdf[coluna] = atributos[coluna].values
    else:  # contagem divergente (registros excluídos?) — não arrisca casar errado
        print(f"  AVISO — {pasta_nome}: {len(atributos)} linhas no .dbf vs "
              f"{len(gdf)} no shapefile; mantendo atributos do GDAL (acentos podem sair errados)")
    gdf = gdf.set_crs(CRS, allow_override=True)
    gdf.to_parquet(CACHE / saida_nome)
    print(f"  {pasta_nome} -> {saida_nome}: {len(gdf)} feições em {time.time()-t0:.1f}s")


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


def construir_db_lotes():
    """LOTE_CTM.parquet -> lotes.duckdb com índice espacial RTREE. Isso é o
    que tira o motor de carregar ~562MB desse arquivo na RAM toda vez que o
    servidor sobe — a consulta passa a ser feita direto no arquivo em disco,
    só varrendo o que está perto do ponto pedido (ver engine/db_lotes.py)."""
    origem = CACHE / "LOTE_CTM.parquet"
    if not origem.exists():
        print("  PULADO — LOTE_CTM.parquet não existe ainda (rode geo_parquet primeiro)")
        return
    destino = CACHE / "lotes.duckdb"
    if destino.exists():
        destino.unlink()
    t0 = time.time()
    con = duckdb.connect(str(destino))
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"""
        CREATE TABLE lotes AS
        SELECT FID, ID_LT, NULOTCTM, ID_QUADRA_CTM, AREA_M2, geometry::GEOMETRY AS geom
        FROM read_parquet('{origem.as_posix()}')
    """)
    con.execute("CREATE INDEX idx_lotes_geom ON lotes USING RTREE (geom)")
    con.close()
    print(f"  LOTE_CTM.parquet -> lotes.duckdb (c/ índice RTREE): {time.time()-t0:.1f}s")


def construir_db_indice():
    """INDICE_CADASTRAL.parquet -> indice_cadastral.duckdb — mesma ideia:
    tira ~180MB de RAM do boot, consulta por NULOTCTM/índice cadastral vira
    uma query pontual em vez de escanear o DataFrame inteiro toda vez."""
    origem = CACHE / "INDICE_CADASTRAL.parquet"
    if not origem.exists():
        print("  PULADO — INDICE_CADASTRAL.parquet não existe ainda")
        return
    destino = CACHE / "indice_cadastral.duckdb"
    if destino.exists():
        destino.unlink()
    t0 = time.time()
    con = duckdb.connect(str(destino))
    con.execute(f"CREATE TABLE indice AS SELECT * FROM read_parquet('{origem.as_posix()}')")
    con.execute("CREATE INDEX idx_indice_nulotctm ON indice (NULOTCTM)")
    con.close()
    print(f"  INDICE_CADASTRAL.parquet -> indice_cadastral.duckdb: {time.time()-t0:.1f}s")


def edificacao_parquet():
    """EDIFICACAO.csv (levantamento aéreo da PBH de 2015: contorno e altura de
    cada construção) -> EDIFICACAO.parquet, ORDENADO por lote (ID_LT) pra
    consulta pontual ler só um pedaço do arquivo.

    Decisões medidas em 09/2026:
    - ALTURA_ESTIMADA, não ALTURA_CALCULADA: as duas só divergem nas 909
      alturas negativas, e a ESTIMADA é a versão corrigida (mínimo 0);
    - descarta altura < 1,5 m e área < 4 m² (ruído do modelo de elevação);
    - coordenadas arredondadas a 10 cm: o arquivo cai de 75 MB para 34 MB,
      com desvio médio de área de 0,36% nas construções >= 20 m². É o que
      mantém o zip de produção leve;
    - OBSERVACAO vira código (os textos vêm com acento corrompido no CSV):
      1 = "Edificação em Construção em 2015", 2 = "altura imprecisa"."""
    origem = CACHE.parent / "EDIFICACAO.csv"
    if not origem.exists():
        print("  PULADO — EDIFICACAO.csv não existe")
        return
    destino = CACHE / "EDIFICACAO.parquet"
    t0 = time.time()
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"""
        COPY (
          SELECT CAST(ID_LOTE_CTM AS BIGINT) AS ID_LT,
                 CAST(round(AREA, 1) AS FLOAT) AS area_m2,
                 CAST(round(ALTURA_ESTIMADA, 1) AS FLOAT) AS altura_m,
                 CASE WHEN OBSERVACAO ILIKE '%constru%' THEN 1
                      WHEN OBSERVACAO ILIKE '%imprecis%' THEN 2 ELSE 0 END::TINYINT AS obs,
                 ST_AsWKB(ST_ReducePrecision(ST_GeomFromText(GEOMETRIA), 0.1)) AS wkb
          FROM read_csv('{origem.as_posix()}', header=true, ignore_errors=true)
          WHERE ALTURA_ESTIMADA >= 1.5 AND AREA >= 4
          ORDER BY ID_LT
        ) TO '{destino.as_posix()}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 8000)
    """)
    con.close()
    print(f"  EDIFICACAO.csv -> EDIFICACAO.parquet: {destino.stat().st_size/1e6:.1f} MB em {time.time()-t0:.1f}s")


def projetos_aprovados_parquet():
    """PROJETO_EDIFICACAO_LICENCIADO (shapefile da PBH com os projetos de
    edificação, atualizado até a véspera do download) -> PROJETOS_APROVADOS.parquet,
    uma linha por projeto com o NULOTCTM do lote onde ele cai.

    - só SITUACAO_P == "APROVADO" (decisão do Arthur: requerimento e
      pendência não entram — "em análise" não é "aprovado");
    - TIPO separa LICENCIAMENTO (obra nova) de REGULARIZACAO (legalização);
    - join ESPACIAL (ponto representativo do projeto dentro do lote do CTM):
      o campo LOTE_PROJE é texto da planta de parcelamento e não casa com o
      CTM. Medido: 99,9% dos projetos caem num lote;
    - data de aprovação = DT_CONCESS, e DATA_APROV (dd/mm/aaaa) quando falta;
    - QTDE_PAVIM fora de 1..60 vira nulo (há valores como 403);
    - LDID=0 no .dbf: atributos lidos por _ler_dbf_latin1."""
    from datetime import date
    shp = CACHE.parent / "PROJETO_EDIFICACAO_LICENCIADO" / "PROJETO_EDIFICACAO_LICENCIADO.shp"
    if not shp.exists():
        print("  PULADO — shapefile PROJETO_EDIFICACAO_LICENCIADO não existe")
        return
    banco_lotes = CACHE / "lotes.duckdb"
    if not banco_lotes.exists():
        print("  PULADO — lotes.duckdb precisa existir antes (é usado no join espacial)")
        return
    t0 = time.time()
    g = gpd.read_file(shp, columns=[]).reset_index(drop=True)
    at = _ler_dbf_latin1(shp.with_suffix(".dbf")).reset_index(drop=True)

    def limpo(serie):
        return serie.astype(str).str.replace("\x00", "", regex=False).str.strip()

    ok = limpo(at["SITUACAO_P"]) == "APROVADO"
    g, at = g[ok].reset_index(drop=True), at[ok].reset_index(drop=True)
    rp = g.geometry.representative_point()
    pts = pd.DataFrame({"i": range(len(g)), "x": rp.x, "y": rp.y})
    con = duckdb.connect(str(banco_lotes), read_only=True)
    con.execute("LOAD spatial;")
    con.register("pts", pts)
    lotes = con.execute(
        "SELECT p.i, l.NULOTCTM FROM pts p JOIN lotes l ON ST_Contains(l.geom, ST_Point(p.x, p.y))"
    ).df()
    con.close()

    def data_iso(serie):
        s = limpo(serie)
        ano = pd.to_numeric(s.str[:4], errors="coerce")
        valida = (s.str.len() == 8) & (ano >= 1900) & (ano <= date.today().year)
        return (s.str[:4] + "-" + s.str[4:6] + "-" + s.str[6:8]).where(valida)

    partes = limpo(at["DATA_APROV"]).str.extract(r"^(\d{2})/(\d{2})/(\d{4})$")
    aprov_alternativa = (partes[2] + "-" + partes[1] + "-" + partes[0]).where(partes[2].notna())
    pav = pd.to_numeric(at["QTDE_PAVIM"], errors="coerce")
    tabela = pd.DataFrame({
        "numero_projeto": limpo(at["NUMERO_PRO"]),
        "tipo": limpo(at["TIPO"]),
        "titulo": limpo(at["TITULO_PRO"]),
        "uso": limpo(at["USO_GERAL"]),
        "dt_aprovacao": data_iso(at["DT_CONCESS"]).fillna(aprov_alternativa),
        "area_construida_m2": pd.to_numeric(at["AREA_CONST"], errors="coerce"),
        "pavimentos": pav.where((pav >= 1) & (pav <= 60)),
        "unidades_res": pd.to_numeric(at["QTD_UND_RE"], errors="coerce"),
        "unidades_nao_res": pd.to_numeric(at["QTD_UND_NA"], errors="coerce"),
        "link_siatu": limpo(at["LINK_SIATU"]).str.extract(r'href="([^"]+)"')[0],
    })
    tabela = lotes.merge(tabela.reset_index().rename(columns={"index": "i"}), on="i").drop(columns="i")
    destino = CACHE / "PROJETOS_APROVADOS.parquet"
    tabela.sort_values("NULOTCTM").to_parquet(destino, compression="zstd", index=False)
    print(f"  PROJETO_EDIFICACAO_LICENCIADO -> PROJETOS_APROVADOS.parquet: {len(tabela)} projetos "
          f"em {tabela.NULOTCTM.nunique()} lotes, {destino.stat().st_size/1e6:.1f} MB, {time.time()-t0:.1f}s")


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

    # shapefiles (encoding do .dbf corrigido na conversão — ver shp_parquet)
    shp_parquet("AREA_PROTECAO_CULTURAL_IPHAN", "PROTECAO_CULTURAL_IPHAN.parquet")
    shp_parquet("AREA_PROTECAO_CULTURAL_IEPHA", "PROTECAO_CULTURAL_IEPHA.parquet")
    shp_parquet("AREA_PROTECAO_CULTURAL_CDPCM-BH", "PROTECAO_CULTURAL_CDPCM.parquet")
    shp_parquet("AREA_PRESERVACAO_PERMANENTE", "APP.parquet")
    indice_cadastral_parquet()
    construir_db_lotes()
    construir_db_indice()
    edificacao_parquet()
    projetos_aprovados_parquet()
    print("Concluído.")
