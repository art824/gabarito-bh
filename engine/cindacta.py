# -*- coding: utf-8 -*-
"""
Restrição de altura por proteção aeronáutica (CINDACTA 1), por PONTO.

Não existe camada pública baixável das superfícies clássicas do aeródromo
(HIN/AT/ACN/VOR etc.) — confirmado tentando os portais BHMap v2 (idebhgeo,
342 camadas) e geosiurbe (webmapsiurbe, 99 camadas via WMS) por WFS/WMS
GetCapabilities, nenhuma bate com essas siglas. A PBH, porém, mantém uma
camada própria com o HISTÓRICO da altura já liberada por lote —
BHMAP_ALTIMETRIA, workspace pbh_geosiurbe — que reflete as atualizações do
CINDACTA ao longo do tempo (validado: os 7 primeiros valores retornados por
essa camada para um lote real bateram, na mesma ordem, com as 7 faixas de
data mostradas no "Informações do Mapa" do BHMap pro mesmo lote).

DECISÃO: consultar essa camada AO VIVO (WFS, por ponto) em vez de baixar as
~400 mil feições — é o mesmo padrão já usado pra geocodificação (Mapbox):
dependência externa aceita, com timeout curto e falha honesta (nunca
bloqueia a ficha inteira se o serviço da PBH estiver fora do ar).

ARMADILHA descoberta testando: o campo "atual" da camada tem o mesmo NOME
("LOTE_CP") de um campo de código de lote usado em OUTRAS camadas do mesmo
workspace — aqui ele contém o valor numérico mais recente da altura, não um
código. Confirmado comparando a ordem/valores com o popup do BHMap.

O valor de cada campo já é a ALTURA em metros (não uma cota a subtrair do
terreno) — confirmado batendo com o IBED real (campo do período vigente
até 18/01/2024 = 29, igual à "Altura máxima: 29m" do IBED).
"""
import re
from datetime import date

import requests

WFS_URL = "http://webmapsiurbe.pbh.gov.br/geosiurbe/ows"
TIPO = "pbh_geosiurbe:BHMAP_ALTIMETRIA"
TIMEOUT_S = 6

# ordem cronológica dos campos datados + rótulo pra exibição (a data de
# início de cada faixa é o fim da faixa anterior + 1 dia; ver popup do BHMap)
_CAMPOS_DATADOS = [
    ("LOTE_CP_ALT_14102015", date(2015, 10, 14), "até 14/10/2015"),
    ("LOTE_CP_ALT_30092018", date(2018, 9, 30), "15/10/2015 a 30/09/2018"),
    ("LOTE_CP_ALT_31082020", date(2020, 8, 31), "01/10/2018 a 31/08/2020"),
    ("LOTE_CP_ALT_21102020", date(2020, 10, 21), "01/09/2020 a 21/10/2020"),
    ("LOTE_CP_ALT_03012021", date(2021, 1, 3), "22/10/2020 a 03/01/2021"),
    ("LOTE_CP_ALT_05012023", date(2023, 1, 5), "04/01/2021 a 04/01/2023"),
    ("LOTE_CP_ALT_22012024", date(2024, 1, 22), "05/01/2023 a 18/01/2024"),
]
_CAMPO_ATUAL = "LOTE_CP"  # nome real da coluna na camada; ver nota acima
_ATUAL_DESDE = "19/01/2024"


class CindactaError(Exception):
    pass


def _num(txt):
    try:
        return float(txt)
    except (TypeError, ValueError):
        return None


def consultar_altimetria_aero(x: float, y: float, buffer_m: float = 2.0) -> dict | None:
    """x, y em EPSG:31983 (mesmo CRS do resto do motor). Devolve None se o
    ponto está fora de qualquer área com restrição registrada (a maior
    parte de BH). Lança CindactaError se o serviço da PBH não responder —
    quem chama decide como avisar o usuário, nunca falha a ficha inteira."""
    bbox = f"{x - buffer_m},{y - buffer_m},{x + buffer_m},{y + buffer_m},EPSG:31983"
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeName": TIPO, "bbox": bbox,
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; GabaritoBH/1.0)"}
    try:
        resp = requests.get(WFS_URL, params=params, headers=headers, timeout=TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise CindactaError(f"Serviço de altimetria aeronáutica da PBH indisponível: {e}")

    xml = resp.text
    if 'numberMatched="0"' in xml:
        return None

    def campo(nome):
        # tag exata (não um prefixo/sufixo de outro campo — ex.: "LOTE_CP"
        # é substring de "ID_LOTE_CP" e de "LOTE_CP_ALT_14102015").
        m = re.search(rf'<{re.escape(nome)}(?:\s[^>]*)?>([^<]*)</{re.escape(nome)}>', xml)
        return _num(m.group(1)) if m else None

    atual = campo(_CAMPO_ATUAL)
    if atual is None:
        return None

    anterior_valor, anterior_periodo = None, None
    for nome, _dt, rotulo in reversed(_CAMPOS_DATADOS):
        v = campo(nome)
        if v is not None:
            anterior_valor, anterior_periodo = v, rotulo
            break

    return {
        "atual_m": atual,
        "atual_desde": _ATUAL_DESDE,
        "anterior_m": anterior_valor,
        "anterior_periodo": anterior_periodo,
    }
