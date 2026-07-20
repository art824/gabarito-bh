# -*- coding: utf-8 -*-
"""
Gabarito — frontend local (landing + consulta), sem login/banco/deploy.
A fase 2 (Supabase + Vercel + freemium) vem depois da validação.

Uso:
    python webapp/app.py
    abrir http://localhost:5000
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "engine"))

from flask import Flask, jsonify, render_template, request
import geopandas as gpd
from shapely.geometry import Point

from consulta import carregar_camadas, consultar, localizar_lote, calcular_testadas, PARAMS, CRS_DADOS
from desenho_lote import (
    orientar_para_desenho, calcular_envelope, calcular_faixa_permeavel,
    calcular_mancha, calcular_altura_maxima, poligono_para_coords,
)
from geocode import endereco_para_latlon, GeocodeError
from indice_cadastral import buscar_por_indice, IndiceCadastralError
from db_lotes import registros_indice_por_nulotctm

app = Flask(__name__)


@app.context_processor
def _asset_versioning():
    """Cache-busting simples: anexa a data de modificação do arquivo como
    query string, pra o navegador nunca servir style.css/script.js
    desatualizado do cache depois de uma mudança (senão precisa hard
    refresh manual pra ver correções)."""
    def versionado(filename):
        from flask import url_for
        caminho = Path(app.static_folder) / filename
        v = int(caminho.stat().st_mtime) if caminho.exists() else 0
        return url_for("static", filename=filename) + f"?v={v}"
    return {"asset": versionado}


print("Carregando camadas geoespaciais (pode levar alguns segundos)...")
ZON, ADE, VIA, EXTRAS = carregar_camadas()
print("Camadas carregadas. Servidor pronto.")

# Rótulos legíveis para as chaves cruas do banco de CA (tabela 10, Anexo XII)
ROTULOS_CA = {
    "ca_min": "CA mín",
    "ca_bas": "CA básico",
    "ca_max": "CA máx",
    "ca_cent": "CA centralidade",
    "qt_m2_un": "Quota (m²/un)",
    "qt_cent_m2_un": "Quota central (m²/un)",
}


def _resolver_amd(via_classe: str, faixa_largura: str, regras) -> float | None:
    """Resolve a AMD (Anexo XII, t.5) pra UM número, usando a via real deste
    lote — em vez de listar todas as classes de via possíveis (que o
    usuário não precisa ver, já que sabemos qual é a via dele)."""
    if not via_classe:
        return None
    for item in regras or []:
        vias = item.get("via", "").split("|")
        if via_classe not in vias:
            continue
        if "amd_m" in item:
            return item["amd_m"]
        # arterial/ligação regional: depende da largura da via
        texto = (faixa_largura or "").replace(" ", "")
        if ">=15m" in texto or ">15m" in texto:
            return item.get("largura>15m")
        return item.get("largura<=15m")
    return None


_AF_JSON = json.loads((PARAMS / "afastamentos_alturas.json").read_text(encoding="utf-8"))


def _afastamento_lateral(altura: float, fator_b: float) -> float:
    """Mesma fórmula da t.4 usada no cliente (script.js) — precisa existir
    também no servidor agora que o envelope é recalculado lá a cada altura."""
    if altura < 8:
        return 1.5
    if altura <= 12:
        return 2.3
    return 2.3 + (altura - 12) / fator_b


def _resolver_af_regra_geral(classe_via: str) -> float | None:
    valor = _AF_JSON["afastamento_frontal"]["regra_geral_por_via"].get(classe_via)
    return valor if isinstance(valor, (int, float)) else None


def _num(v):
    """Converte para float se der; senão None (nunca inventa valor)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _montar_estudo(res: dict) -> dict | None:
    """Dados numéricos p/ o bloco interativo da ficha (planta + calculadora).
    Usa os valores crus ANTES da conversão das exceções para texto."""
    if not res.get("zoneamento"):
        return None
    ficha = res.get("ficha", {})
    ca = ficha.get("coef_aproveitamento") or {}

    af_val = ficha.get("afastamento_frontal_m")
    af_num = af_val if isinstance(af_val, (int, float)) else None

    # exceção de AF numérica prevalece (ex.: ADE Pampulha = 5,0)
    af_exc, af_exc_ade = None, None
    for e in ficha.get("excecoes_incidentes", []):
        if e.get("tema") == "Afastamento frontal":
            n = _num(e.get("regra"))
            if n is not None:
                af_exc, af_exc_ade = n, e.get("ade")

    quota = _num(ca.get("qt_m2_un"))

    # % numéricos de TP/TO (ex.: "20%" -> 20.0; "40% (ADE...)" -> 40.0)
    import re as _re
    def _pct(txt):
        m = _re.match(r"\s*(\d+(?:[.,]\d+)?)\s*%", str(txt or ""))
        return float(m.group(1).replace(",", ".")) if m else None

    # Fator B da t.4 (confirmado no doc oficial): 8 p/ CR/AGEE/AGEUC/OP-3;
    # 6 em centralidade local; 4 nas demais. Quando a camada de Centralidade
    # Local identificou o lote, usamos o valor REAL em vez do conservador.
    sigla = res["zoneamento"]["sigla"]
    lote_real = res.get("lote_real")
    if sigla in ("CR", "AGEE", "AGEUC", "OP-3"):
        fator_b = 8
    elif lote_real and lote_real.get("centralidade_local"):
        fator_b = 6
    else:
        fator_b = 4
    fator_b_real = bool(lote_real and "centralidade_local" in lote_real)

    # testada/área reais do CTM, quando o lote foi identificado com confiança
    # e a geometria não é complexa demais (mais de 2 ruas confrontantes)
    testada_real, area_real = None, None
    if lote_real and not lote_real.get("geometria_complexa") and lote_real.get("testadas"):
        testada_real = max(t["comprimento_m"] for t in lote_real["testadas"])
        area_real = lote_real.get("area_m2")

    return {
        "sigla": sigla,
        "ca_bas": _num(ca.get("ca_bas")),
        "ca_max": _num(ca.get("ca_max")),
        "quota": quota,
        "quota_sem_limite": ca.get("qt_m2_un") == "sem_limite",
        "af": af_num,
        "af_texto": "sem exigência" if af_num is None else None,
        "af_exc": af_exc,
        "af_exc_ade": af_exc_ade,
        "tp_txt": ficha.get("taxa_permeabilidade_min"),
        "to_txt": ficha.get("taxa_ocupacao_max"),
        "tp_pct": _pct(ficha.get("taxa_permeabilidade_min")),
        "to_pct": _pct(ficha.get("taxa_ocupacao_max")),
        "fator_b": fator_b,
        "fator_b_real": fator_b_real,
        "via_classe": (res.get("via_mais_proxima") or {}).get("classificacao"),
        "testada_real": testada_real,
        "area_real": area_real,
    }


def _SIM_NAO(v):
    if v is None:
        return None
    return "Sim" if str(v).strip().upper() == "SIM" else "Não"


def _montar_identificacao(res: dict, extras: dict, indice_consultado: str | None = None) -> dict | None:
    """Bloco 'Identificação do lote' — junta com o cadastro imobiliário (IPTU)
    pelo NULOTCTM achado via CTM. Espelha o relatório do SIURBE.

    Um lote pode ter VÁRIAS unidades (economias) no IPTU, cada uma com seu
    índice cadastral. Quando a busca foi por índice, exibimos exatamente a
    unidade consultada — devolver a "primeira do banco" fazia o site mostrar
    um índice diferente do digitado (bug real apontado pela K2)."""
    lote_real = res.get("lote_real")
    if not lote_real or not lote_real.get("nulotctm"):
        return None
    con_indice = extras.get("indice_cadastral")
    if con_indice is None:
        return None

    nulotctm = lote_real["nulotctm"]
    registros = registros_indice_por_nulotctm(con_indice, nulotctm)
    if not registros:
        return None

    def _norm_indice(s):
        return re.sub(r"\s+", "", str(s or "")).upper()

    # ordem do banco é arbitrária — ordenar deixa a lista legível e a
    # "primeira unidade" exibida determinística entre consultas
    registros.sort(key=lambda r: _norm_indice(r.get("INDICE_CADASTRAL")))
    registro = registros[0]
    unidade_consultada = False
    if indice_consultado:
        alvo = _norm_indice(indice_consultado)
        for r in registros:
            if _norm_indice(r.get("INDICE_CADASTRAL")) == alvo:
                registro = r
                unidade_consultada = True
                break
    n_economias = len(registros)
    indices_lote = [r.get("INDICE_CADASTRAL") for r in registros if r.get("INDICE_CADASTRAL")]

    setor, quadra, lote_ctm_num = (nulotctm[:2], nulotctm[2:7], nulotctm[7:]) if len(nulotctm) == 12 else (None, None, None)

    area_terreno = _num(registro.get("AREA_TERRENO"))
    area_ctm = lote_real.get("area_m2")
    divergencia = None
    if area_terreno and area_ctm and area_terreno > 0:
        dif_pct = abs(area_terreno - area_ctm) / area_ctm * 100
        if dif_pct > 15:
            divergencia = f"IPTU declara {area_terreno:g} m², CTM calcula {area_ctm:g} m² — divergência de {dif_pct:.0f}%, conferir."

    infra = {
        "Meio-fio": _SIM_NAO(registro.get("IND_MEIO_FIO")),
        "Pavimentação": _SIM_NAO(registro.get("IND_PAVIMENTACAO")),
        "Arborização": _SIM_NAO(registro.get("IND_ARBORIZACAO")),
        "Galeria pluvial": _SIM_NAO(registro.get("IND_GALERIA_PLUVIAL")),
        "Iluminação pública": _SIM_NAO(registro.get("IND_ILUMINACAO_PUBLICA")),
        "Rede de esgoto": _SIM_NAO(registro.get("IND_REDE_ESGOTO")),
        "Rede de água": _SIM_NAO(registro.get("IND_REDE_AGUA")),
        "Rede telefônica": _SIM_NAO(registro.get("IND_REDE_TELEFONICA")),
    }

    edificacao = None
    ano = registro.get("ANO_CONSTRUCAO")
    if ano and str(ano).strip():
        edificacao = {
            "tipo_construtivo": registro.get("TIPO_CONSTRUTIVO"),
            "tipo_ocupacao": registro.get("TIPO_OCUPACAO"),
            "padrao_acabamento": registro.get("PADRAO_ACABAMENTO"),
            "ano_construcao": ano,
            "area_construcao": _num(registro.get("AREA_CONSTRUCAO")),
        }

    return {
        "indice_cadastral": registro.get("INDICE_CADASTRAL"),
        "unidade_consultada": unidade_consultada,
        "indices_lote": indices_lote,
        "endereco_iptu": " ".join(
            str(p) for p in [registro.get("TIPO_LOGRADOURO"), registro.get("NOME_LOGRADOURO"),
                              registro.get("NUMERO_IMOVEL")] if p and str(p).strip()
        ),
        "cep": registro.get("CEP"),
        "setor": setor, "quadra": quadra, "lote_ctm_num": lote_ctm_num,
        "area_terreno_iptu": area_terreno,
        "area_ctm": area_ctm,
        "divergencia_area": divergencia,
        "infra": infra,
        "n_economias": n_economias,
        "edificacao": edificacao,
    }


def _montar_veredito(res: dict) -> dict | None:
    """Síntese "pode construir?" pro topo da ficha (pedido da K2, pensando em
    corretores). REGRA DE OURO: nunca afirmar além do que as bases mostram —
    o veredito diz o que foi verificado, o que pede atenção e o que NÃO foi
    verificado, sempre com origem."""
    if not res.get("zoneamento"):
        return None
    ficha = res.get("ficha", {})
    ca = ficha.get("coef_aproveitamento") or {}

    def _pct(txt):
        m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*%", str(txt or ""))
        return float(m.group(1).replace(",", ".")) if m else None

    to_pct = _pct(ficha.get("taxa_ocupacao_max"))
    tp_pct = _pct(ficha.get("taxa_permeabilidade_min"))

    atencoes = []
    if to_pct is not None and to_pct <= 10:
        atencoes.append(
            f"Parâmetros muito restritivos nesta zona: ocupação máxima de {to_pct:g}% "
            f"do terreno (camada de TP/TO do BHMAP)."
        )
    if res.get("ades"):
        atencoes.append(
            "Lote dentro de ADE (" + ", ".join(res["ades"]) + ") — exceções da ADE "
            "prevalecem sobre a regra geral; confira as exceções na ficha."
        )
    for alerta in res.get("alertas", []):
        if "não verificad" not in alerta:
            atencoes.append(alerta)

    nao_verificado = [
        "Altura máxima de aeródromo (CINDACTA/DECEA)",
        "Área de Preservação Permanente (APP) e meio ambiente",
        "Patrimônio cultural (proteções e tombamentos)",
    ]
    nao_verificado += [a.rstrip(".") for a in res.get("alertas", []) if "não verificad" in a]

    ca_bas = ca.get("ca_bas")
    verificado = []
    if ca_bas is not None:
        verificado.append(
            f"O zoneamento ({res['zoneamento']['sigla']}) permite construir — "
            f"coeficiente básico {ca_bas:g} (até {ca_bas:g}× a área do terreno, "
            f"sem contrapartida). Fonte: Anexo XII, t.10."
        )
    if to_pct is not None and tp_pct is not None:
        verificado.append(
            f"Ocupação máxima de {to_pct:g}% e permeabilidade mínima de {tp_pct:g}% "
            f"do terreno. Fonte: camada TP/TO do BHMAP + t.11."
        )

    return {"verificado": verificado, "atencoes": atencoes, "nao_verificado": nao_verificado}


def _texto_regra(regra) -> str:
    """Regra de exceção pode ser str, dict ou lista — vira texto legível."""
    if isinstance(regra, dict):
        partes = []
        for k, v in regra.items():
            if k == "requer_setor":
                continue
            partes.append(f"{k.replace('_', ' ')}: {_texto_regra(v)}")
        return "; ".join(partes)
    if isinstance(regra, list):
        return "; ".join(_texto_regra(item) for item in regra)
    return str(regra)


@app.route("/", methods=["GET"])
def landing():
    return render_template("landing.html")


@app.route("/consulta", methods=["GET", "POST"])
def consulta_page():
    contexto = {
        "resultado": None, "erro": None, "endereco": "", "indice_cadastral": "",
        "modo": "endereco",
        "rotulos_ca": ROTULOS_CA, "amd_valor": None,
        "estudo": None, "identificacao": None, "veredito": None,
    }
    if request.method == "GET":
        return render_template("consulta.html", **contexto)

    modo = request.form.get("modo", "endereco")
    contexto["modo"] = modo

    if modo == "indice":
        indice = request.form.get("indice_cadastral", "").strip()
        contexto["indice_cadastral"] = indice
        if not indice:
            contexto["erro"] = "Digite um índice cadastral para consultar."
            return render_template("consulta.html", **contexto)
        try:
            g = buscar_por_indice(indice, EXTRAS.get("indice_cadastral"), EXTRAS.get("lote_ctm"))
        except IndiceCadastralError as e:
            contexto["erro"] = str(e)
            return render_template("consulta.html", **contexto)
    else:
        endereco = request.form.get("endereco", "").strip()
        contexto["endereco"] = endereco
        if not endereco:
            contexto["erro"] = "Digite um endereço para consultar."
            return render_template("consulta.html", **contexto)
        try:
            g = endereco_para_latlon(endereco)
        except GeocodeError as e:
            contexto["erro"] = str(e)
            return render_template("consulta.html", **contexto)
        # Resultado genérico (bairro/cidade) geraria ficha de um ponto arbitrário —
        # melhor recusar com clareza do que fingir precisão.
        if g.get("tipo") not in ("address", "street"):
            contexto["erro"] = (
                f"Não encontramos um endereço específico para \"{endereco}\" — o resultado "
                f"mais próximo foi \"{g['nome_encontrado']}\", genérico demais para localizar "
                "um lote. Confira a grafia e inclua rua e número, se possível."
            )
            return render_template("consulta.html", **contexto)

    res = consultar(g["lat"], g["lon"], ZON, ADE, VIA, EXTRAS)
    res["geocodificado_como"] = g["nome_encontrado"]
    contexto["resultado"] = res

    ficha = res.get("ficha", {})
    via_info = res.get("via_mais_proxima") or {}
    contexto["amd_valor"] = _resolver_amd(
        via_info.get("classificacao"), via_info.get("faixa_largura"),
        ficha.get("altura_maxima_divisa"),
    )
    estudo = _montar_estudo(res)  # antes de virar texto, p/ pegar valores crus
    if estudo is not None:
        estudo["lat"] = g["lat"]
        estudo["lon"] = g["lon"]
        estudo["desenho_inicial"] = _calcular_desenho(g["lat"], g["lon"], 9.0, res=res)
        # FALHA HONESTA (princípio da K2): melhor "indisponível" do que um
        # desenho possivelmente errado. Três estados em que não confiamos no
        # desenho automático — cai no modo manual com aviso explícito.
        lote_real = res.get("lote_real")
        estudo["anexo_indisponivel"] = None
        if lote_real and lote_real.get("geometria_complexa"):
            estudo["anexo_indisponivel"] = (
                "Este lote confronta 3 ou mais ruas — o desenho automático ainda não "
                "cobre esse caso com segurança. Abaixo, um estudo genérico com medidas "
                "editáveis (não é o desenho real do lote)."
            )
        elif estudo.get("testada_real") and estudo["desenho_inicial"] is None:
            estudo["anexo_indisponivel"] = (
                "Não foi possível calcular o desenho deste lote com segurança. Abaixo, "
                "um estudo genérico com medidas editáveis (não é o desenho real do lote)."
            )
        elif estudo["desenho_inicial"] and estudo["desenho_inicial"].get("inconstruivel"):
            estudo["anexo_indisponivel"] = (
                "O modelo de afastamentos não encontrou área construível em nenhuma "
                "altura para o formato deste lote — pode ser limitação do modelo em "
                "formatos muito irregulares, não necessariamente do lote. Para não "
                "exibir um desenho enganoso, o anexo automático fica indisponível. "
                "Abaixo, um estudo genérico com medidas editáveis."
            )
        if estudo["anexo_indisponivel"]:
            # zera o modo "lote real" — o template e o script caem no modo manual
            estudo["testada_real"] = None
            estudo["area_real"] = None
            estudo["desenho_inicial"] = None
    contexto["estudo"] = estudo
    contexto["identificacao"] = _montar_identificacao(
        res, EXTRAS,
        indice_consultado=contexto["indice_cadastral"] if modo == "indice" else None,
    )
    contexto["veredito"] = _montar_veredito(res)
    for exc in ficha.get("excecoes_incidentes", []):
        exc["regra"] = _texto_regra(exc["regra"])
    return render_template("consulta.html", **contexto)


def _calcular_desenho(lat: float, lon: float, altura: float, res: dict | None = None,
                       altura_maxima_conhecida: float | None = None) -> dict | None:
    """Núcleo geométrico do anexo interativo — usado tanto no primeiro
    render (`/consulta`, altura padrão) quanto nas atualizações do slider
    (`/consulta/estudo`). Sempre relocaliza o lote (barato, local) em vez
    de guardar estado de sessão."""
    ponto = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(CRS_DADOS).iloc[0]
    achado = localizar_lote(ponto, EXTRAS.get("lote_ctm"))
    if achado is None:
        return None

    poly = achado["poly"]
    testadas_info = calcular_testadas(poly, VIA)
    testadas = testadas_info["testadas"]
    if testadas_info["geometria_complexa"] or not testadas:
        return None

    if res is None:
        res = consultar(lat, lon, ZON, ADE, VIA, EXTRAS)
    estudo = _montar_estudo(res)
    if estudo is None:
        return None

    poly_d, _angulo = orientar_para_desenho(poly, testadas)

    af_por_rua = {t["rua"]: _resolver_af_regra_geral(t.get("classificacao")) for t in testadas}

    # faixa de TP não depende da altura (só do contorno/testadas) — calcula
    # uma vez só e reaproveita tanto na altura pedida quanto na busca da
    # altura máxima abaixo
    faixa_tp_base = None
    if estudo.get("tp_pct") is not None:
        area_min = poly_d.area * estudo["tp_pct"] / 100
        faixa_tp_base = calcular_faixa_permeavel(poly_d, testadas, area_min)
    to_m2_max = poly_d.area * estudo["to_pct"] / 100 if estudo.get("to_pct") is not None else None

    # altura máxima de VERDADE pra esse lote — o slider não pode ir além
    # do ponto em que a projeção construível já não tem área nenhuma
    # (calculado por lote, não um teto fixo igual pra todos). É uma
    # varredura sequencial (ver desenho_lote.py), mais cara que uma busca
    # binária — por isso só roda de fato na 1ª carga da página; as
    # chamadas seguintes do slider já mandam o valor de volta e a gente
    # só reaproveita, em vez de recalcular a cada arrastada.
    if altura_maxima_conhecida is not None:
        altura_maxima = altura_maxima_conhecida
    else:
        altura_maxima = calcular_altura_maxima(
            poly_d, testadas, af_por_rua, estudo.get("af_exc"), estudo["fator_b"],
            faixa_tp_base, to_m2_max,
        )
    altura_usada = min(altura, altura_maxima)

    lateral_m = _afastamento_lateral(altura_usada, estudo["fator_b"])

    envelope = calcular_envelope(poly_d, testadas, af_por_rua, estudo.get("af_exc"), lateral_m)
    inconstruivel = envelope is None

    faixa_tp = faixa_tp_base if not inconstruivel else None

    mancha, limitante = (None, None)
    if not inconstruivel:
        mancha, limitante = calcular_mancha(envelope, faixa_tp, to_m2_max)

    return {
        "inconstruivel": inconstruivel,
        "lateral_m": round(lateral_m, 2),
        "altura_maxima": altura_maxima,
        "altura_usada": round(altura_usada, 1),
        "contorno": poligono_para_coords(poly_d),
        "testadas": [{"rua": t["rua"], "comprimento_m": t["comprimento_m"],
                       "classificacao": t.get("classificacao"),
                       "indices_arestas": t["indices_arestas"]} for t in testadas],
        "area_total": round(poly_d.area, 1),
        "envelope": poligono_para_coords(envelope) if envelope is not None else None,
        "envelope_area": round(envelope.area, 1) if envelope is not None else None,
        "faixa_tp": poligono_para_coords(faixa_tp) if faixa_tp is not None else None,
        "faixa_tp_area": round(faixa_tp.area, 1) if faixa_tp is not None else None,
        "mancha": poligono_para_coords(mancha) if mancha is not None else None,
        "mancha_area": round(mancha.area, 1) if mancha is not None else None,
        "mancha_limitante": limitante,
    }


@app.route("/consulta/estudo", methods=["POST"])
def consulta_estudo():
    """Recalcula o envelope construtivo (polígono real, recuo não-uniforme)
    pra uma altura pretendida. Chamado pelo slider do anexo interativo."""
    dados = request.get_json(silent=True) or {}
    try:
        lat = float(dados.get("lat"))
        lon = float(dados.get("lon"))
        altura = float(dados.get("altura"))
    except (TypeError, ValueError):
        return jsonify({"erro": "parâmetros inválidos"}), 400

    # o front manda de volta a altura_maxima que já recebeu na carga
    # inicial — evita recalcular a varredura sequencial (mais cara) a
    # cada arrastada do slider, já que o valor não muda pro mesmo lote
    altura_maxima_conhecida = None
    try:
        if dados.get("altura_maxima") is not None:
            altura_maxima_conhecida = float(dados["altura_maxima"])
    except (TypeError, ValueError):
        pass

    desenho = _calcular_desenho(lat, lon, altura, altura_maxima_conhecida=altura_maxima_conhecida)
    if desenho is None:
        return jsonify({"erro": "lote não identificado ou geometria complexa demais"}), 422
    return jsonify(desenho)


@app.route("/reportar-desenho", methods=["POST"])
def reportar_desenho():
    """Grava um relato de 'o desenho não bate' — sem banco, só um arquivo
    JSONL local pro Arthur revisar e ajustar o motor depois. Não bloqueia
    nem exige nada do usuário."""
    dados = request.get_json(silent=True) or {}
    registro = {
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "lat": dados.get("lat"), "lon": dados.get("lon"),
        "endereco": dados.get("endereco"),
        "tipo": dados.get("tipo"),
        "comentario": (dados.get("comentario") or "").strip()[:500],
    }
    caminho = BASE / "data" / "relatos_desenho.jsonl"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return jsonify({"ok": True})


if __name__ == "__main__":
    import os
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
