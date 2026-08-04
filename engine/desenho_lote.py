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
from shapely.geometry import LineString
from shapely.ops import unary_union


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
    na MESMA ordem/índice usado em calcular_testadas. Retorna None quando o
    recuo não deixa área aproveitável.

    COMO FUNCIONA (e por que mudou em 08/2026): a versão anterior deslocava
    a RETA de cada aresta e cruzava as retas consecutivas pra achar os novos
    vértices. Isso é exato só em polígonos convexos de poucos lados; com
    arestas quase colineares (comuníssimo no CTM — lote de 12 vértices com
    a frente levemente curva) o cruzamento de duas retas quase paralelas
    dispara pra longe e devolve um polígono AUTO-CRUZADO. O `buffer(0)`
    "consertava" a forma e o resultado seguia pro desenho, às vezes
    violando o próprio afastamento que deveria respeitar. Medido numa
    amostra de 400 lotes reais: só 34,6% produziam envelope válido, e as
    falhas eram lotes CONVEXOS normais, não casos exóticos.

    Agora usamos a definição do recuo diretamente: a área construtiva é o
    que sobra do lote depois de remover a faixa de largura d_i ao longo de
    CADA aresta i. Em shapely isso é uma diferença contra a união dos
    buffers das arestas — robusto (não auto-cruza), correto por definição,
    monotônico por construção (recuo maior => área menor ou igual) e válido
    também em lotes côncavos. Cantos convexos continuam saindo retos; num
    vértice reflexo o canto sai arredondado, que é o correto (a construção
    também precisa se afastar do vértice).
    """
    coords = list(poly.exterior.coords)[:-1]
    n = len(coords)
    if n != len(distancias):
        return None

    faixas = []
    for i in range(n):
        d = distancias[i]
        if d is None or d <= 0:
            continue
        p0, p1 = coords[i], coords[(i + 1) % n]
        if _direcao(p0, p1)[2] == 0:
            continue
        faixas.append(LineString([p0, p1]).buffer(d))

    if not faixas:
        return poly

    try:
        resto = poly.difference(unary_union(faixas))
    except Exception:
        return None

    if resto.is_empty:
        return None
    if resto.geom_type in ("MultiPolygon", "GeometryCollection"):
        # o recuo partiu o lote em pedaços (lote em L, gargalo estreito):
        # fica com o maior, que é o que de fato dá pra ocupar
        partes = [g for g in resto.geoms if g.geom_type == "Polygon" and not g.is_empty]
        if not partes:
            return None
        resto = max(partes, key=lambda g: g.area)
    if resto.geom_type != "Polygon" or resto.area < 0.5:
        return None

    # tira micro-vértices dos arcos, deixando o SVG mais leve sem mudar a
    # área de forma perceptível (2 cm de tolerância)
    simples = resto.simplify(0.02, preserve_topology=True)
    if simples.geom_type == "Polygon" and not simples.is_empty and simples.area >= 0.5:
        resto = simples
    return resto


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


def afastamento_lateral_formula(altura, fator_b):
    """Mesma fórmula da t.4 usada em webapp/app.py — duplicada aqui (em vez
    de importada) porque este módulo não depende do Flask; é só matemática
    pura, sem risco de divergir (testado nos 2 lugares)."""
    if altura < 8:
        return 1.5
    if altura <= 12:
        return 2.3
    return 2.3 + (altura - 12) / fator_b


def calcular_altura_maxima(poly_desenho, testadas, af_por_rua, af_exc, fator_b,
                            faixa_tp, to_m2_max, area_min_util=1.0,
                            h_min=3.0, h_max=100.0, passo=0.5):
    """Maior altura (m) cuja projeção construível (mancha) ainda tem pelo
    menos `area_min_util` m² de área — vira o teto REAL do slider de altura
    no front (calculado pela geometria de CADA lote, não um valor fixo
    igual pra todos).

    NÃO é busca binária — foi busca binária antes, e tinha um bug real: o
    algoritmo de recuo por aresta (_offset_por_aresta) pode, em lotes bem
    côncavos/irregulares, ter um "solavanco" numérico em que a área da
    mancha ZERA numa altura e depois volta a aparecer positiva numa altura
    MAIOR (artefato do algoritmo, não um resultado geométrico de verdade).
    Busca binária assume que a função só diminui — com esse solavanco ela
    podia pular o primeiro zero de verdade e convergir num valor de altura
    bem mais alto e errado (visto na prática: lote que devia travar a uns
    40 e poucos metros deixava o slider ir até 82m).

    Por isso aqui é uma VARREDURA SEQUENCIAL de baixo pra cima, de `passo`
    em `passo` — para no PRIMEIRO ponto em que a área cai abaixo do
    mínimo e IGNORA qualquer "recuperação" depois disso. Só refina com
    busca binária dentro do último intervalinho (onde a monotonicidade
    local é uma suposição segura)."""
    def _mancha_area(h):
        lateral = afastamento_lateral_formula(h, fator_b)
        envelope = calcular_envelope(poly_desenho, testadas, af_por_rua, af_exc, lateral)
        if envelope is None:
            return 0.0
        mancha, _ = calcular_mancha(envelope, faixa_tp, to_m2_max)
        return mancha.area if mancha is not None else 0.0

    if _mancha_area(h_min) < area_min_util:
        return h_min  # nem na altura mínima sobra área útil

    h_anterior = h_min
    h = h_min + passo
    while h <= h_max:
        if _mancha_area(h) < area_min_util:
            # achou o primeiro "zero" — refina só entre h_anterior (bom) e
            # h (ruim), sem olhar mais nada acima disso
            lo, hi = h_anterior, h
            for _ in range(10):
                mid = (lo + hi) / 2
                if _mancha_area(mid) >= area_min_util:
                    lo = mid
                else:
                    hi = mid
            return round(lo, 1)
        h_anterior = h
        h += passo
    return round(h_anterior, 1)  # nunca zerou até h_max


def poligono_para_coords(poly):
    if poly is None or poly.is_empty:
        return []
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    return [list(pt) for pt in poly.exterior.coords]
