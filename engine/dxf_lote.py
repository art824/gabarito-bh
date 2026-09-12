# -*- coding: utf-8 -*-
"""
Exporta o estudo do lote (contorno + envelope + faixa permeável + projeção)
como arquivo DXF, pra abrir direto no CAD.

DECISÃO DE COORDENADAS: o anexo interativo trabalha num referencial GIRADO
(`orientar_para_desenho` roda o lote pra testada ficar horizontal embaixo —
bom pra desenhar na tela, ruim pra CAD). O DXF sai em UTM REAL (SIRGAS 2000
/ zona 23S, EPSG:31983), o mesmo das plantas da Prefeitura, pra o arquivo
poder ser sobreposto a levantamento topográfico, outro lote, ou imagem
georreferenciada sem ninguém ter que girar nada na mão.

Como a volta é feita: o contorno no referencial de desenho e o polígono
original têm os MESMOS vértices, na mesma ordem (girar e transladar não
reordenam nada). Então dois pontos correspondentes bastam pra achar a
rotação+translação inversa — é uma transformação rígida, exata, sem
aproximação.

Dependência: `ezdxf`, Python puro (sem biblioteca de sistema). Isso é
requisito, não detalhe: foi exatamente por exigir cairo/pango que o
WeasyPrint foi descartado na geração de PDF (ver CLAUDE.md).
"""
import math
from io import BytesIO

import ezdxf

# cores ACI (índice de cor do AutoCAD) por camada
_COR = {
    "LOTE": 7,             # branco/preto conforme fundo
    "ENVELOPE": 1,         # vermelho
    "TAXA_PERMEAVEL": 3,   # verde
    "PROJECAO_MAXIMA": 5,  # azul
    "INFO": 8,             # cinza
}


def _transformacao_para_utm(contorno_desenho, poly_original):
    """Devolve f(x, y) -> (x_utm, y_utm), invertendo o giro do desenho.

    Retorna a identidade se não der pra estabelecer correspondência (lote
    sem testada identificada nunca chega a ser girado, então identidade é
    de fato o certo nesse caso).
    """
    a = [tuple(p) for p in (contorno_desenho or [])]
    b = list(poly_original.exterior.coords)
    if len(a) < 2 or len(b) < 2:
        return lambda x, y: (x, y)

    # remove o ponto de fechamento, se houver, dos dois lados
    if len(a) > 1 and a[0] == a[-1]:
        a = a[:-1]
    if len(b) > 1 and b[0] == b[-1]:
        b = b[:-1]
    if len(a) != len(b) or len(a) < 2:
        return lambda x, y: (x, y)

    ax, ay = a[0]
    bx, by = b[0]
    theta = (math.atan2(b[1][1] - by, b[1][0] - bx)
             - math.atan2(a[1][1] - ay, a[1][0] - ax))
    cos_t, sin_t = math.cos(theta), math.sin(theta)

    def f(x, y):
        dx, dy = x - ax, y - ay
        return (bx + dx * cos_t - dy * sin_t,
                by + dx * sin_t + dy * cos_t)

    return f


def _validar(f, contorno_desenho, poly_original, tol=0.05):
    """Confere que a transformação realmente recoloca o contorno em cima do
    polígono original. Se errar mais que `tol` (5 cm) em qualquer vértice,
    é melhor não exportar georreferenciado do que exportar torto."""
    a = [tuple(p) for p in contorno_desenho]
    b = list(poly_original.exterior.coords)
    if len(a) > 1 and a[0] == a[-1]:
        a = a[:-1]
    if len(b) > 1 and b[0] == b[-1]:
        b = b[:-1]
    if len(a) != len(b):
        return False
    for (x, y), (bx, by) in zip(a, b):
        fx, fy = f(x, y)
        if math.hypot(fx - bx, fy - by) > tol:
            return False
    return True


def gerar_dxf(desenho: dict, poly_original, meta: dict | None = None) -> bytes:
    """Monta o DXF a partir do dicionário que `_calcular_desenho` devolve.

    `desenho` traz os anéis já calculados (contorno, envelope, faixa_tp,
    mancha) no referencial de desenho; `poly_original` é o polígono do lote
    como está no Cadastro Técnico, usado pra devolver tudo ao UTM real.
    """
    meta = meta or {}
    f = _transformacao_para_utm(desenho.get("contorno"), poly_original)
    georreferenciado = _validar(f, desenho.get("contorno") or [], poly_original)
    if not georreferenciado:
        f = lambda x, y: (x, y)  # noqa: E731 — cai no referencial do desenho

    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # 6 = metros; faz o CAD saber a escala
    msp = doc.modelspace()
    for nome, cor in _COR.items():
        if nome not in doc.layers:
            doc.layers.add(nome, color=cor)

    def poli(coords, camada):
        if not coords:
            return
        pts = [f(float(p[0]), float(p[1])) for p in coords]
        msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": camada})

    poli(desenho.get("contorno"), "LOTE")
    poli(desenho.get("envelope"), "ENVELOPE")
    poli(desenho.get("faixa_tp"), "TAXA_PERMEAVEL")
    poli(desenho.get("mancha"), "PROJECAO_MAXIMA")

    # bloco de texto com a procedência — o arquivo circula solto, longe do
    # site, então ele precisa dizer sozinho de onde veio e o que não é
    linhas = [
        "GABARITO - gabaritoarq.com.br",
        f"Lote: {meta.get('indice') or meta.get('endereco') or '-'}",
        f"Area do lote (CTM): {desenho.get('area_total')} m2",
        f"Altura considerada: {desenho.get('altura_usada')} m",
        f"Afastamento lateral: {desenho.get('lateral_m')} m",
        f"Area do envelope: {desenho.get('envelope_area')} m2",
        f"Projecao maxima: {desenho.get('mancha_area')} m2",
        f"Emitido em: {meta.get('data') or '-'}",
        ("Coordenadas: SIRGAS 2000 / UTM 23S (EPSG:31983)"
         if georreferenciado else
         "ATENCAO: sem georreferenciamento, coordenadas locais do desenho"),
        "ESTUDO PRELIMINAR - nao substitui responsavel tecnico",
        "nem consulta oficial a Prefeitura de Belo Horizonte.",
    ]
    try:
        minx, miny, _, _ = poly_original.bounds if georreferenciado else (0, 0, 0, 0)
        if not georreferenciado:
            xs = [p[0] for p in (desenho.get("contorno") or [[0, 0]])]
            ys = [p[1] for p in (desenho.get("contorno") or [[0, 0]])]
            minx, miny = min(xs), min(ys)
        y = miny - 4.0
        for linha in linhas:
            msp.add_text(
                linha,
                dxfattribs={"layer": "INFO", "height": 1.0},
            ).set_placement((minx, y))
            y -= 1.6
    except Exception:
        pass  # o desenho importa; a legenda é acessório

    buf = BytesIO()
    doc.write(buf, fmt="bin")
    return buf.getvalue()
