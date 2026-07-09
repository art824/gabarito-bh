# -*- coding: utf-8 -*-
"""
Motor de consulta — Fase 1 (validação, sem site)
Recebe coordenada (lat/lon WGS84) e devolve a ficha urbanística do ponto.

Uso:
    python3 consulta.py -19.9245 -43.9352
    python3 consulta.py -19.9245 -43.9352 --json

Camadas usadas (EPSG:31983 - SIRGAS 2000 / UTM 23S):
    ZONEAMENTO_11181  -> sigla do zoneamento (Anexo I da Lei 11.181/19)
    ADE_11181         -> ADEs incidentes (Anexo III)
    CLASSIFICACAO_VIARIA_11181 -> via mais próxima e sua classificação (Anexos V/VI)

Limitações conhecidas (v0 do motor — NÃO usar comercialmente ainda):
    - Sem camada do Anexo II (estrutura ambiental): TO/TP não são emitidas.
    - Sem setores internos de ADE: exceções que dependem de setor viram alerta.
    - Sem camadas de OUC/PVP/conexões de fundo de vale: emitido apenas aviso genérico.
    - "Via do lote" = via mais próxima do ponto; para lotes de esquina, conferir manualmente.
"""
import sys, json, argparse
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from geocode import endereco_para_latlon, GeocodeError
from db_lotes import conectar_lotes, conectar_indice, lote_mais_proximo, registros_indice_por_nulotctm

BASE = Path(__file__).resolve().parent.parent
GEO = BASE / "data" / "geo"
CACHE = GEO / "_cache"
PARAMS = BASE / "data" / "params"

CRS_DADOS = "EPSG:31983"

# distância máx. (m) do lote CTM mais próximo p/ considerar "identificado com confiança"
LIMIAR_LOTE_M = 20
# distância máx. (m) de uma aresta do lote a uma via p/ contar como testada
LIMIAR_CONFRONTO_M = 15

# ADEs cujas exceções dependem de setor interno que ainda não temos mapeado
ADES_COM_SETOR = {
    "ADE Avenida do Contorno", "ADE Bacia da Pampulha", "ADE Pampulha",
    "ADE Buritis", "ADE Sao Bento", "ADE Regiao da Lagoinha",
    "ADE Santa Tereza", "ADE Venda Nova", "ADE Mirantes",
}


def _cache_ou_none(nome_parquet: str):
    caminho = CACHE / nome_parquet
    if not caminho.exists():
        return None
    if nome_parquet.endswith(".parquet") and nome_parquet != "INDICE_CADASTRAL.parquet":
        return gpd.read_parquet(caminho)
    return pd.read_parquet(caminho)


def carregar_camadas():
    zon = gpd.read_file(GEO / "ZONEAMENTO_11181" / "ZONEAMENTO_11181.shp")
    ade = gpd.read_file(GEO / "ADE_11181" / "ADE_11181.shp")
    via = gpd.read_file(GEO / "CLASSIFICACAO_VIARIA_11181" / "CLASSIFICACAO_VIARIA_11181.shp")
    extras = {
        "tp": gpd.read_file(GEO / "TAXA_PERMEABILIDADE_11181" / "TAXA_PERMEABILIDADE_11181.shp"),
        "fundo_vale": gpd.read_file(GEO / "CONEXAO_FUNDO_VALE" / "CONEXAO_FUNDO_VALE.shp"),
        "ade_amb": gpd.read_file(GEO / "ADE_INTERESSE_AMBIENTAL_11181" / "ADE_INTERESSE_AMBIENTAL_11181.shp"),
        "conexao_verde": gpd.read_file(GEO / "CONEXAO_VERDE_11181" / "CONEXAO_VERDE_11181.shp"),
    }

    # lote_ctm e indice_cadastral NÃO carregam mais o arquivo inteiro na RAM
    # (eram ~562MB e ~180MB) — viram conexões DuckDB read-only, consultadas
    # sob demanda por ponto/chave (engine/db_lotes.py). Ver CLAUDE.md.
    con_lotes = conectar_lotes()
    if con_lotes is None:
        print("AVISO: data/geo/_cache/lotes.duckdb não encontrado — "
              "rode 'python scripts/preparar_dados.py'. Testada/área real ficará indisponível.",
              file=sys.stderr)
    extras["lote_ctm"] = con_lotes
    extras["centralidade"] = _cache_ou_none("CENTRALIDADE_LOCAL.parquet")
    extras["recuo"] = _cache_ou_none("RECUO_ALINHAMENTO.parquet")
    extras["indice_cadastral"] = conectar_indice()
    extras["ade_setores"] = _cache_ou_none("ADE_SETORES.parquet")
    extras["bairro_oficial"] = _cache_ou_none("BAIRRO_OFICIAL.parquet")
    extras["bairro_popular"] = _cache_ou_none("BAIRRO_POPULAR.parquet")
    extras["proj_viario"] = _cache_ou_none("PROJ_VIARIO_PRIOR.parquet")

    return zon, ade, via, extras


def localizar_lote(ponto, con_lotes, limiar_m: float = LIMIAR_LOTE_M):
    """Acha o lote CTM mais próximo do ponto, consultando o DuckDB indexado
    (não carrega mais o arquivo inteiro na memória). None se não houver
    conexão ou se a distância exceder o limiar (lote não identificado com
    confiança)."""
    achado = lote_mais_proximo(con_lotes, ponto.x, ponto.y, limiar_m)
    if achado is None:
        return None
    poly = achado["poly"]
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    # orientação CANÔNICA (sentido anti-horário) — precisa ser feita uma
    # única vez aqui, porque calcular_testadas() e preparar_desenho_lote()
    # dependem dos MESMOS índices de aresta pra combinar via/AF com o
    # polígono; reorientar depois quebraria essa correspondência.
    from shapely.geometry.polygon import orient
    poly = orient(poly, sign=1.0)
    return {"row": achado["row"], "poly": poly, "distancia_m": achado["distancia_m"]}


def _paralela_o_bastante(edge_dx, edge_dy, edge_len, via_geom, ponto_medio, limiar_cos=0.66):
    """True se a aresta do lote correr aprox. paralela à via no ponto mais
    próximo (tangente local, passo de 2m). Sem isso, uma aresta LATERAL do
    lote (perpendicular à rua) que por acaso caia perto da via entra na soma
    da testada e infla o valor pro tamanho do lado comprido — bug real
    encontrado testando lotes estreitos e profundos (comuns em BH)."""
    if edge_len == 0:
        return False
    proj = via_geom.project(ponto_medio)
    passo = 2.0
    p_a = via_geom.interpolate(max(proj - passo, 0))
    p_b = via_geom.interpolate(min(proj + passo, via_geom.length))
    vdx, vdy = p_b.x - p_a.x, p_b.y - p_a.y
    vlen = (vdx ** 2 + vdy ** 2) ** 0.5
    if vlen == 0:
        return False
    cos = abs((edge_dx * vdx + edge_dy * vdy) / (edge_len * vlen))
    return cos > limiar_cos


def calcular_testadas(poly, via, limiar_confronto_m: float = LIMIAR_CONFRONTO_M):
    """Decompõe o contorno do lote em arestas e atribui cada uma à via mais
    próxima; agrupa por via (só as dentro do limiar E paralelas à via —
    arestas laterais/de fundo são descartadas, mesmo se estiverem perto).
    Guarda também QUAIS arestas (índices) e a via em si de cada grupo —
    necessário pra desenhar o envelope com AF por rua em lotes de esquina
    (cada rua pode ter classificação/AF diferente). Vias muito longe do
    lote inteiro já são descartadas antes, por bbox, pra não testar contra
    440k trechos."""
    coords = list(poly.exterior.coords)
    via_prox = via[via.distance(poly) < limiar_confronto_m + 10]
    if via_prox.empty:
        return {"testadas": [], "geometria_complexa": False}

    from shapely.geometry import LineString
    grupos = {}  # nome -> {comprimento_m, via (row), indices_arestas}
    for i in range(len(coords) - 1):
        p0, p1 = coords[i], coords[i + 1]
        seg = LineString([p0, p1])
        if seg.length < 0.3:
            continue
        meio = seg.interpolate(0.5, normalized=True)
        dists = via_prox.distance(meio)
        idx_min = dists.idxmin()
        if dists.loc[idx_min] >= limiar_confronto_m:
            continue
        v = via_prox.loc[idx_min]
        edx, edy = p1[0] - p0[0], p1[1] - p0[1]
        if not _paralela_o_bastante(edx, edy, seg.length, v.geometry, meio):
            continue
        nome = f"{v['TP_LOG']} {v['NO_LOG']}"
        if nome not in grupos:
            grupos[nome] = {"comprimento_m": 0.0, "via": v, "indices_arestas": []}
        grupos[nome]["comprimento_m"] += seg.length
        grupos[nome]["indices_arestas"].append(i)

    testadas = [
        {
            "rua": nome, "comprimento_m": round(g["comprimento_m"], 1),
            "classificacao": g["via"].get("CLASSIFICA"),
            "faixa_largura": g["via"].get("DESCRICAO_"),
            "indices_arestas": g["indices_arestas"],
        }
        for nome, g in sorted(grupos.items(), key=lambda x: -x[1]["comprimento_m"])
    ]
    return {"testadas": testadas, "geometria_complexa": len(testadas) > 2}


# Tabela 11 do Anexo XII: TP mínima -> TO máxima
TP_PARA_TO = {95.0: "3%", 70.0: "25%", 30.0: "60%", 20.0: "80%"}


def consultar(lat: float, lon: float, zon, ade, via, extras=None) -> dict:
    ponto = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(CRS_DADOS).iloc[0]

    r = {"entrada": {"lat": lat, "lon": lon}, "alertas": []}

    # 1. Zoneamento (ponto em polígono)
    hit = zon[zon.contains(ponto)]
    if hit.empty:
        r["alertas"].append("Ponto fora de qualquer polígono de zoneamento — endereço fora de BH ou em área não mapeada.")
        r["zoneamento"] = None
        return r
    r["zoneamento"] = {
        "sigla": hit.iloc[0]["SIGLA_TIPO"],
        "descricao": hit.iloc[0]["DESC_TIPO_"],
    }

    # 2. ADEs incidentes (pode haver mais de uma sobreposta)
    ades_hit = ade[ade.contains(ponto)]
    r["ades"] = ades_hit["NOME_ADE"].tolist()

    # setor interno da ADE (Anexo VII) — identificado por geometria quando a
    # camada existe; antes disso, tudo virava alerta genérico "não identificado"
    setores_ade = extras.get("ade_setores") if extras else None
    r["ade_setor_nome"] = None
    if setores_ade is not None and not setores_ade.empty:
        setor_hit = setores_ade[setores_ade.contains(ponto)]
        if not setor_hit.empty:
            r["ade_setor_nome"] = setor_hit.iloc[0]["NOME_SETOR_ADE"]

    for nome in r["ades"]:
        if nome in ADES_COM_SETOR:
            if r["ade_setor_nome"]:
                r["alertas"].append(
                    f"'{nome}' possui setores internos — setor identificado: \"{r['ade_setor_nome']}\". "
                    "Confira no Anexo VII se há regra específica para esse setor (ainda não automatizado item a item)."
                )
            else:
                r["alertas"].append(
                    f"'{nome}' possui SETORES internos com regras distintas; o setor deste lote não pôde ser identificado (fora da camada de setores). Conferir manualmente o Anexo VII."
                )

    # 2b. Bairro oficial/popular e Projeto Viário Prioritário
    bo = extras.get("bairro_oficial") if extras else None
    if bo is not None and not bo.empty:
        hit_bo = bo[bo.contains(ponto)]
        r["bairro_oficial"] = hit_bo.iloc[0]["NOME"] if not hit_bo.empty else None
    else:
        r["bairro_oficial"] = None
    bp = extras.get("bairro_popular") if extras else None
    if bp is not None and not bp.empty:
        hit_bp = bp[bp.contains(ponto)]
        r["bairro_popular"] = hit_bp.iloc[0]["NOME"] if not hit_bp.empty else None
    else:
        r["bairro_popular"] = None
    pv = extras.get("proj_viario") if extras else None
    if pv is not None and not pv.empty and not pv[pv.contains(ponto)].empty:
        r["alertas"].append("Lote atingido por Projeto Viário Prioritário — pode haver previsão de desapropriação/alargamento; conferir na PBH.")

    # 3. Via mais próxima (aprox. da via do lote)
    dist = via.distance(ponto)
    idx = dist.idxmin()
    v = via.loc[idx]
    r["via_mais_proxima"] = {
        "nome": f"{v['TP_LOG']} {v['NO_LOG']}",
        "classificacao": v["CLASSIFICA"],
        "faixa_largura": v.get("DESCRICAO_"),
        "distancia_m": round(float(dist.loc[idx]), 1),
    }
    if dist.loc[idx] > 40:
        r["alertas"].append("Via mais próxima a mais de 40 m do ponto — geocodificação pode ter caído no meio da quadra; confira a via correta.")

    # 3b. Lote real (CTM): área, testadas por rua confrontante, Centralidade
    # Local, Conexão Verde e proximidade de recuo de alinhamento
    r["lote_real"] = None
    if extras and extras.get("lote_ctm") is not None:
        achado = localizar_lote(ponto, extras["lote_ctm"])
        if achado is None:
            r["alertas"].append("Lote não identificado com confiança na base cadastral (CTM) — testada e área do estudo interativo ficam manuais.")
        else:
            poly = achado["poly"]
            testada_info = calcular_testadas(poly, via)
            area_oficial = achado["row"].get("AREA_M2")
            lote_real = {
                "nulotctm": achado["row"].get("NULOTCTM"),
                "area_m2": float(area_oficial) if area_oficial is not None else round(poly.area, 1),
                "testadas": testada_info["testadas"],
                "geometria_complexa": testada_info["geometria_complexa"],
                "distancia_m": achado["distancia_m"],
            }
            if testada_info["geometria_complexa"]:
                r["alertas"].append(
                    f"Lote confronta com {len(testada_info['testadas'])} vias distintas — geometria complexa demais para calcular testada automaticamente; conferir manualmente."
                )
            if extras.get("centralidade") is not None:
                lote_real["centralidade_local"] = not extras["centralidade"][extras["centralidade"].contains(ponto)].empty
            if extras.get("conexao_verde") is not None:
                lote_real["conexao_verde"] = not extras["conexao_verde"][extras["conexao_verde"].contains(ponto)].empty
            r["lote_real"] = lote_real

    if extras and extras.get("recuo") is not None and not extras["recuo"].empty:
        recuo_prox = extras["recuo"][extras["recuo"].distance(ponto) < 15]
        if not recuo_prox.empty:
            trecho = recuo_prox.iloc[0]
            largura = trecho.get("LARGURA_FINAL_TRECHO")
            r["alertas"].append(
                f"Lote próximo a trecho com previsão de recuo de alinhamento "
                f"(largura final prevista: {largura} m) — conferir Planta de Parcelamento."
            )

    # 4. Parâmetros pela sigla
    ca = json.loads((PARAMS / "ca_quota.json").read_text(encoding="utf-8"))
    af = json.loads((PARAMS / "afastamentos_alturas.json").read_text(encoding="utf-8"))

    sigla = r["zoneamento"]["sigla"]
    ficha = {}

    linha_ca = ca["regra_geral"].get(sigla)
    if linha_ca is None:
        r["alertas"].append(f"Sigla '{sigla}' sem linha correspondente no banco de CA — mapear.")
    elif any(v == "VERIFICAR" for v in map(str, linha_ca.values())):
        r["alertas"].append(f"Parâmetros de CA para '{sigla}' ainda não conferidos no documento oficial (marcados VERIFICAR).")
        ficha["coef_aproveitamento"] = linha_ca
    else:
        ficha["coef_aproveitamento"] = linha_ca

    classe_via = r["via_mais_proxima"]["classificacao"]
    af_geral = af["afastamento_frontal"]["regra_geral_por_via"].get(classe_via, "classificação de via não mapeada")
    ficha["afastamento_frontal_m"] = af_geral
    ficha["afastamentos_laterais_fundos"] = af["afastamentos_laterais_fundos"]["regra_geral"]
    ficha["altura_maxima_divisa"] = af["altura_maxima_divisa"]["regra_geral"]

    # 5. Exceções por ADE — aplicadas de forma conservadora: mostradas, nunca silenciosas
    excecoes = []
    for nome in r["ades"]:
        for bloco, chave in [("ca_quota", "excecoes_ade"), ("afastamentos", None)]:
            pass
        exc_ca = ca["excecoes_ade"].get(nome)
        if exc_ca:
            excecoes.append({"ade": nome, "tema": "CA/Quota", "regra": exc_ca.get("regra", exc_ca)})
        exc_af = af["afastamento_frontal"]["excecoes_ade"].get(nome)
        if exc_af is not None:
            excecoes.append({"ade": nome, "tema": "Afastamento frontal", "regra": exc_af})
        exc_alt = af["limite_altimetria"]["por_ade"].get(nome)
        if exc_alt is not None:
            excecoes.append({"ade": nome, "tema": "Limite de altimetria", "regra": exc_alt})
    ficha["excecoes_incidentes"] = excecoes

    # 6. TP/TO pela camada do Anexo II + sobreposições ambientais
    if extras:
        tp_hit = extras["tp"][extras["tp"].contains(ponto)]
        if not tp_hit.empty:
            tp_val = float(tp_hit.iloc[0]["TAXA_PERME"])
            ficha["taxa_permeabilidade_min"] = f"{tp_val:g}%"
            ficha["taxa_ocupacao_max"] = TP_PARA_TO.get(tp_val, "conferir tabela 11")
            msg = tp_hit.iloc[0].get("MENSAGEM_P")
            if isinstance(msg, str) and msg.strip():
                ficha["tp_observacao"] = msg
            if "ADE Cidade Jardim" in r["ades"]:
                ficha["taxa_ocupacao_max"] = "40% (ADE Cidade Jardim, t.11 nota 5 — prevalece)"
        else:
            r["alertas"].append("Ponto fora da camada de taxa de permeabilidade — TO/TP não determinadas.")

        fv = extras["fundo_vale"]
        if not fv[fv.contains(ponto)].empty:
            ficha.setdefault("excecoes_incidentes", excecoes).append({
                "ade": "Conexão de fundo de vale", "tema": "TP/TO e CA",
                "regra": "TP 70% / TO 25% e CAbas restrito a 0,5 (sem CAmax/CAcent/CAmin) até elaboração do PEA — t.11 nota 6 e t.10",
            })

        amb = extras["ade_amb"]
        amb_hit = amb[amb.contains(ponto)]
        if not amb_hit.empty:
            nome_amb = amb_hit.iloc[0]["NOME_TIPO_"]
            r["ades"].append(nome_amb)
            r["alertas"].append(f"Ponto em {nome_amb}: TO aplicável a todos os níveis inclusive subsolo (t.11 nota 1); demais diretrizes específicas não automatizadas.")

    # 7. Avisos estruturais do v0
    # (o aviso de setor de ADE já é emitido por ADE, de forma específica, no
    # passo 2 — usando a camada ADE_SETORES quando disponível; não repetir
    # aqui um aviso genérico que hoje seria simplesmente falso.)
    r["alertas"].append("Sobreposições de OUC e PVP não verificadas (camadas não incorporadas).")

    r["ficha"] = ficha
    return r


def formatar(r: dict) -> str:
    L = []
    L.append("=" * 62)
    L.append("FICHA URBANÍSTICA (v0 — validação interna, não usar em projeto)")
    L.append("=" * 62)
    if r.get("zoneamento"):
        z = r["zoneamento"]
        L.append(f"Zoneamento ....... {z['sigla']} — {z['descricao']}")
    L.append(f"ADEs ............. {', '.join(r.get('ades', [])) or 'nenhuma'}")
    if "via_mais_proxima" in r:
        v = r["via_mais_proxima"]
        L.append(f"Via provável ..... {v['nome']} ({v['classificacao']}, {v['faixa_largura']}, a {v['distancia_m']} m)")
    f = r.get("ficha", {})
    if f.get("coef_aproveitamento"):
        c = f["coef_aproveitamento"]
        L.append("Coef. Aproveit. .. " + ", ".join(f"{k}={v}" for k, v in c.items() if k != "obs"))
        if c.get("obs"):
            L.append(f"                   obs: {c['obs']}")
    L.append(f"Afast. frontal ... {f.get('afastamento_frontal_m')}")
    if f.get("taxa_permeabilidade_min"):
        L.append(f"TP mínima ........ {f['taxa_permeabilidade_min']}   |   TO máxima: {f.get('taxa_ocupacao_max')}")
        if f.get("tp_observacao"):
            L.append(f"                   obs: {f['tp_observacao'][:120]}")
    if f.get("excecoes_incidentes"):
        L.append("-" * 62)
        L.append("EXCEÇÕES INCIDENTES (prevalecem sobre a regra geral):")
        for e in f["excecoes_incidentes"]:
            L.append(f"  • [{e['ade']} / {e['tema']}] {e['regra']}")
    if r.get("alertas"):
        L.append("-" * 62)
        L.append("ALERTAS:")
        for a in r["alertas"]:
            L.append(f"  ⚠ {a}")
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("lat", type=float, nargs="?")
    ap.add_argument("lon", type=float, nargs="?")
    ap.add_argument("--endereco", type=str, help="endereço em BH (usa geocodificação Mapbox em vez de lat/lon)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.endereco:
        try:
            g = endereco_para_latlon(args.endereco)
        except GeocodeError as e:
            print(f"ERRO de geocodificação: {e}")
            sys.exit(1)
        print(f"[geocodificado: {g['nome_encontrado']}]")
        lat, lon = g["lat"], g["lon"]
    elif args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
    else:
        ap.error("informe lat lon OU --endereco")

    zon, ade, via, extras = carregar_camadas()
    res = consultar(lat, lon, zon, ade, via, extras)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    else:
        print(formatar(res))
