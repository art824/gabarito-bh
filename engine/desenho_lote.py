# -*- coding: utf-8 -*-
"""
Geometria do anexo interativo: transforma o polígono real do lote (CTM)
num referencial de desenho (testada embaixo, y crescendo pro fundo) e
calcula o envelope construtivo com recuo NÃO uniforme — AF nas arestas de
testada (uma por rua confrontante, cada uma com seu próprio AF quando é
esquina) e afastamento lateral/fundos nas demais arestas.

Tudo em metros, no CRS local do lote (EPSG:31983) até a rotação; depois da
rotação as coordenadas já estão prontas pro SVG (só escalar e inverter Y).
"""
import math

from shapely.affinity import rotate, translate
from shapely.geometry import Polygon, LineString


def _direcao(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    comp = math.hypot(dx, dy)
    return (dx, dy, comp)


def orientar_para_desenho(poly, testadas):
    """Rotaciona+translada o polígono (já CCW) pra que a maior testada
    fique horizontal, na base, com o interior do lote crescendo em +y.
    Retorna (poly_desenho, angulo_graus, indice_referencia)."""
    if not testadas or not testadas[0].get("indices_arestas"):
        # sem testada identificada: sem referência de rotação, usa o menor
        # retângulo envolvente como aproximação (raro — geralmente só
        # ocorre se calcular_testadas não achou via nenhuma por perto)
        return poly, 0.0

    coords = list(poly.exterior.coords)[:-1]
    n = len(coords)
    ref_i = testadas[0]["indices_arestas"][0]
    p0, p1 = coords[ref_i], coords[(ref_i + 1) % n]
    dx, dy, _ = _direcao(p0, p1)
    angulo = math.degrees(math.atan2(dy, dx))

    centro = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    girado = rotate(poly, -angulo, origin=centro, use_radians=False)

    # confere se o interior ficou ACIMA da aresta de referência (y crescente);
    # se não, gira mais 180° (o sentido de caminhada CCW às vezes deixa o
    # interior no lado oposto dependendo de qual ponta da aresta é p0/p1)
    y_aresta = girado.exterior.interpolate(0).y if False else None
    gc = girado.centroid
    ref_coords = list(girado.exterior.coords)[:-1]
    ry0, ry1 = ref_coords[ref_i][1], ref_coords[(ref_i + 1) % n][1]
    y_medio_aresta = (ry0 + ry1) / 2
    if gc.y < y_medio_aresta:
        girado = rotate(girado, 180, origin=centro, use_radians=False)
        angulo += 180

    # translada pra aresta de referência ficar em y=0, centralizada em x=0
    ref_coords2 = list(girado.exterior.coords)[:-1]
    rp0, rp1 = ref_coords2[ref_i], ref_coords2[(ref_i + 1) % n]
    meio_x = (rp0[0] + rp1[0]) / 2
    meio_y = (rp0[1] + rp1[1]) / 2
    final = translate(girado, xoff=-meio_x, yoff=-meio_y)
    return final, angulo


def _offset_por_aresta(poly, distancias):
    """Recuo com distância própria por aresta. `distancias` é uma lista do
    mesmo tamanho que os vértices do exterior (sem o ponto de fechamento),
    na MESMA ordem/índice usado em calcular_testadas. Interior deve estar
    à esquerda de cada aresta (polígono CCW). Retorna None se o resultado
    não for um polígono simples válido (recuo grande demais / lote em L)."""
    coords = list(poly.exterior.coords)[:-1]
    n = len(coords)
    if n != len(distancias):
        return None

    linhas = []
    for i in range(n):
        p0, p1 = coords[i], coords[(i + 1) % n]
        dx, dy, comp = _direcao(p0, p1)
        if comp == 0:
            linhas.append(None)
            continue
        ux, uy = dx / comp, dy / comp
        nx, ny = -uy, ux  # normal à esquerda = interior, p/ CCW
        d = distancias[i]
        ox, oy = p0[0] + nx * d, p0[1] + ny * d
        linhas.append((ox, oy, ux, uy))

    def interseccao(a, b):
        ax, ay, adx, ady = a
        bx, by, bdx, bdy = b
        denom = adx * bdy - ady * bdx
        if abs(denom) < 1e-9:
            return None
        t = ((bx - ax) * bdy - (by - ay) * bdx) / denom
        return (ax + adx * t, ay + ady * t)

    novos = []
    for i in range(n):
        a = linhas[i - 1]
        b = linhas[i]
        if a is None or b is None:
            return None
        pt = interseccao(a, b)
        if pt is None:
            return None
        novos.append(pt)

    try:
        candidato = Polygon(novos)
    except Exception:
        return None
    if not candidato.is_valid:
        candidato = candidato.buffer(0)
    if candidato.is_empty or candidato.geom_type != "Polygon" or not candidato.is_valid:
        return None
    if candidato.area < 0.5:
        return None
    # sanidade: um recuo pra dentro NUNCA pode ultrapassar o polígono
    # original. O algoritmo de interseção de retas consecutivas (sem
    # clipping de vértice reflexo) pode produzir uma forma auto-cruzada
    # que passa no is_valid mas "escapa" pra fora em lotes bem côncavos —
    # descoberto testando com recuo grande num lote real (área aumentava
    # em vez de diminuir). Se isso acontecer, tratamos como recuo grande
    # demais pra esse algoritmo (mesmo efeito de "inconstruível").
    if not poly.buffer(0.05).contains(candidato):
        return None
    return candidato


def calcular_envelope(poly_desenho, testadas, af_por_rua, af_exc, lateral_m):
    """Monta o vetor de distâncias por aresta (AF nas arestas de cada
    testada — seu próprio valor se for esquina; afastamento lateral nas
    demais) e calcula o envelope. `af_por_rua`: {nome_rua: af_m}."""
    coords = list(poly_desenho.exterior.coords)[:-1]
    n = len(coords)
    distancias = [lateral_m] * n

    for t in testadas:
        af_desta_rua = af_exc if af_exc is not None else af_por_rua.get(t["rua"])
        if af_desta_rua is None:
            continue
        for i in t.get("indices_arestas", []):
            if i < n:
                distancias[i] = af_desta_rua

    return _offset_por_aresta(poly_desenho, distancias)


def calcular_faixa_permeavel(poly_desenho, testadas, area_min_m2):
    """Faixa de TP: recuo uniforme a partir da aresta de FUNDOS (a mais
    distante do conjunto de arestas de testada), crescendo até atingir a
    área mínima exigida. Busca binária simples na distância de recuo."""
    if area_min_m2 is None or area_min_m2 <= 0:
        return None
    area_total = poly_desenho.area
    if area_min_m2 >= area_total:
        return poly_desenho  # TP exigida cobre o lote inteiro

    coords = list(poly_desenho.exterior.coords)[:-1]
    n = len(coords)
    indices_testada = {i for t in testadas for i in t.get("indices_arestas", [])}
    # "recuo a partir do fundo" = todas as arestas QUE NÃO são testada
    # recebem o mesmo recuo cravado; arestas de testada ficam com recuo 0
    # (a faixa permeável cresce da frente pro fundo)

    from shapely.geometry import Polygon as _Poly

    def area_com_recuo(d):
        distancias = [0.0 if i in indices_testada else d for i in range(n)]
        return _offset_por_aresta(poly_desenho, distancias)

    # Queremos o MENOR recuo cuja área permeável resultante já atinge o
    # mínimo exigido (a faixa mais estreita possível que ainda cumpre a
    # TP) — ou seja, o ínfimo de d tal que permeavel(d) >= area_min_m2.
    # área permeável CRESCE com d (testado e confirmado monótono na faixa
    # válida do algoritmo), então: satisfez -> tenta d MENOR (hi=mid);
    # não satisfez -> precisa de d MAIOR (lo=mid). Tinha ficado invertido
    # numa primeira versão — bug real: convergia pro maior d válido em vez
    # do menor, e a faixa saía enorme (quase o lote inteiro).
    lo, hi = 0.0, 200.0
    melhor = _Poly()
    for _ in range(28):
        mid = (lo + hi) / 2
        env = area_com_recuo(mid)
        if env is None:
            # recuo grande demais pro algoritmo calcular com confiança —
            # não sabemos se satisfaz; joga a busca pra baixo (mais seguro)
            hi = mid
            continue
        area_permeavel = area_total - env.area
        if area_permeavel >= area_min_m2:
            hi = mid
            melhor = env
        else:
            lo = mid
    # a faixa permeável é o lote MENOS a área recuada (a parte perto da testada)
    try:
        faixa = poly_desenho.difference(melhor) if not melhor.is_empty else poly_desenho
    except Exception:
        return None
    if faixa.is_empty:
        return None
    return faixa


def calcular_mancha(envelope, faixa_tp, to_m2_max):
    """Projeção construída dentro do envelope: primeiro tira a faixa
    permeável obrigatória (não se constrói em cima dela); se ainda assim
    sobrar mais área que a TO permite, encolhe a mancha em direção à
    testada (escala a partir do ponto médio da base do envelope) até
    caber no limite de TO. É uma aproximação — o recorte exato "started
    da frente pro fundo" para um polígono arbitrário exigiria outro
    algoritmo de recorte; a escala mantém a silhueta real em vez de virar
    retângulo, que é o que importa pra fidelidade visual."""
    if envelope is None or envelope.is_empty:
        return None, None
    tem_tp = faixa_tp is not None and not faixa_tp.is_empty
    bruta = envelope.difference(faixa_tp) if tem_tp else envelope
    if bruta.is_empty:
        return None, "afastamentos + TP"
    if to_m2_max is None or bruta.area <= to_m2_max:
        # nada precisou encolher pela TO — o que limitou foi o envelope
        # (afastamentos) e, se houver, a faixa de TP também
        limitante = "afastamentos + TP" if tem_tp else "afastamentos"
        return bruta, limitante

    # precisa encolher: escala em torno do ponto médio da base (y mínimo,
    # que é a frente — convenção de orientar_para_desenho: testada em y=0)
    minx, miny, maxx, maxy = bruta.bounds
    origem = ((minx + maxx) / 2, miny)
    from shapely.affinity import scale as _scale

    lo, hi = 0.0, 1.0
    melhor = bruta
    for _ in range(24):
        mid = (lo + hi) / 2
        candidato = _scale(bruta, xfact=mid, yfact=mid, origin=origem)
        if candidato.area <= to_m2_max:
            lo = mid
            melhor = candidato
        else:
            hi = mid
    return melhor, "TO"


def poligono_para_coords(poly):
    if poly is None or poly.is_empty:
        return []
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return [list(pt) for pt in poly.exterior.coords]
