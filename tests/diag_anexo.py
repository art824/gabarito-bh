# -*- coding: utf-8 -*-
"""
Diagnóstico PROFUNDO do anexo interativo — pipeline inteiro, não só o
envelope. Complementa tests/cobertura_anexo.py (que mede só se o recuo
geométrico sai).

Aqui a pergunta é: "o anexo entrega uma experiência correta e coerente
pro usuário que mexe no slider?". Checa, por lote:

  FALHA_PIPELINE  — não produziu desenho nenhum
  CONGELA         — o desenho para de responder ao slider antes do teto
                    (servidor trava a altura, cliente segue mostrando
                    número maior: o usuário arrasta e nada muda)
  NAO_MONOTONICO  — área construtiva sobe quando a altura sobe
  VIOLA_AF        — a mancha desenhada invade o afastamento frontal
  LENTO           — 1ª carga acima do orçamento (o slider fica travado)

    python tests/diag_anexo.py [n_amostra]
"""
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "engine"))
sys.path.insert(0, str(BASE / "webapp"))

from shapely.geometry import Point, LineString, Polygon  # noqa: E402

ORCAMENTO_1A_CARGA_S = 1.5   # acima disso a consulta fica visivelmente lenta
TOL_AF = 0.10                # 10 cm: tolerância de desenho


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    import app as A  # importa depois do sys.path

    con = A.EXTRAS["lote_ctm"]
    rows = con.execute(
        "SELECT NULOTCTM, ST_X(ST_Centroid(geom)), ST_Y(ST_Centroid(geom)) "
        f"FROM lotes USING SAMPLE {n} ROWS"
    ).fetchall()

    import geopandas as gpd
    problemas = {"FALHA_PIPELINE": [], "CONGELA": [], "NAO_MONOTONICO": [],
                 "VIOLA_AF": [], "LENTO": []}
    testados = 0
    tempos = []

    for nul, x, y in rows:
        ll = gpd.GeoSeries([Point(x, y)], crs="EPSG:31983").to_crs("EPSG:4326").iloc[0]
        lat, lon = ll.y, ll.x

        t0 = time.time()
        try:
            d0 = A._calcular_desenho(lat, lon, 9.0)
        except Exception as e:
            problemas["FALHA_PIPELINE"].append((nul, f"exceção: {e}"))
            continue
        dt = time.time() - t0
        if d0 is None:
            continue  # lote complexo/sem testada: fora de escopo, não é falha
        testados += 1
        tempos.append(dt)
        if dt > ORCAMENTO_1A_CARGA_S:
            problemas["LENTO"].append((nul, f"{dt:.2f}s"))

        hmax = d0["altura_maxima"]
        contorno = d0["contorno"]
        idx_testada = set()
        for t in d0["testadas"]:
            idx_testada.update(t["indices_arestas"])

        # varre o slider de 3 m até o teto anunciado
        alturas = [3.0]
        h = 6.0
        while h <= hmax:
            alturas.append(round(h, 1))
            h += max(1.0, (hmax - 3) / 12)
        if alturas[-1] != hmax:
            alturas.append(hmax)

        ant_area = None
        congelou_em = None
        ultimo_usado = None
        for H in alturas:
            d = A._calcular_desenho(lat, lon, H, altura_maxima_conhecida=hmax)
            if d is None:
                problemas["FALHA_PIPELINE"].append((nul, f"None em H={H}"))
                break
            usado = d["altura_usada"]
            # CONGELA: o servidor devolve altura menor que a pedida (clamp)
            if usado < H - 0.05 and congelou_em is None:
                congelou_em = (H, usado)
            ultimo_usado = usado

            area = 0.0 if d["inconstruivel"] else (d["mancha_area"] or 0.0)
            if ant_area is not None and area > ant_area + 0.5:
                problemas["NAO_MONOTONICO"].append(
                    (nul, f"H={H}: {ant_area} -> {area}"))
                break
            ant_area = area

            # VIOLA_AF: mancha invade o afastamento frontal
            if d["mancha"]:
                man = Polygon(d["mancha"])
                for i in idx_testada:
                    p0, p1 = contorno[i], contorno[i + 1]
                    seg = LineString([p0, p1])
                    af_exigido = None
                    # o AF real usado está implícito; recupera pela distância
                    # mínima esperada: compara com o envelope, que respeita AF
                    if d["envelope"]:
                        env = Polygon(d["envelope"])
                        af_exigido = seg.distance(env)
                    if af_exigido is None:
                        continue
                    if seg.distance(man) < af_exigido - TOL_AF:
                        problemas["VIOLA_AF"].append(
                            (nul, f"H={H}: mancha a {seg.distance(man):.2f} m, "
                                  f"envelope a {af_exigido:.2f} m"))
                        break

        if congelou_em is not None:
            problemas["CONGELA"].append(
                (nul, f"pediu {congelou_em[0]} m, desenhou {congelou_em[1]} m "
                      f"(teto anunciado {hmax})"))

    print()
    print(f"lotes com anexo disponível: {testados} (de {n} sorteados)")
    if tempos:
        tempos.sort()
        print(f"1ª carga: mediana {tempos[len(tempos)//2]:.2f}s | "
              f"pior {tempos[-1]:.2f}s | orçamento {ORCAMENTO_1A_CARGA_S}s")
    print()
    for chave, itens in problemas.items():
        pct = 100 * len(itens) / testados if testados else 0
        print(f"{chave:16s} {len(itens):4d}  ({pct:5.1f}%)")
        for it in itens[:4]:
            print(f"                   ex: {it}")


if __name__ == "__main__":
    main()
