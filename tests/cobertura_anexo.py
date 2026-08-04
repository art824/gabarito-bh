# -*- coding: utf-8 -*-
"""
Mede a COBERTURA do anexo interativo numa amostra de lotes reais.

Meta declarada pelo Arthur: funcionar bem em ~90% dos lotes; os
excepcionalmente complexos podem cair honestamente em "indisponível".
Sem este número, "melhorei o desenho" é opinião — com ele, é medida.

    python tests/cobertura_anexo.py [n_amostra]
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "engine"))
sys.path.insert(0, str(BASE / "webapp"))

from consulta import carregar_camadas, localizar_lote, calcular_testadas  # noqa: E402
import desenho_lote as dl                                                  # noqa: E402
from shapely.geometry import Point                                         # noqa: E402


def amostrar(con, n):
    return con.execute(
        "SELECT NULOTCTM, ST_X(ST_Centroid(geom)), ST_Y(ST_Centroid(geom)) "
        f"FROM lotes USING SAMPLE {n} ROWS"
    ).fetchall()


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    print(f"Carregando camadas... (amostra de {n} lotes)")
    ZON, ADE, VIA, EXTRAS = carregar_camadas()
    con = EXTRAS["lote_ctm"]

    tot = {"lote": 0, "testada": 0, "complexa": 0, "orienta": 0,
           "envelope": 0, "inconstruivel_h9": 0, "ok": 0}
    falhas_exemplo = []

    for nul, x, y in amostrar(con, n):
        pt = Point(x, y)
        achado = localizar_lote(pt, con)
        if achado is None:
            continue
        tot["lote"] += 1
        poly = achado["poly"]
        ti = calcular_testadas(poly, VIA)
        if not ti["testadas"]:
            continue
        tot["testada"] += 1
        if ti["geometria_complexa"]:
            tot["complexa"] += 1
            continue  # 3+ ruas: fora de escopo por decisão, não conta como falha

        try:
            p, _ang = dl.orientar_para_desenho(poly, ti["testadas"])[:2]
        except Exception:
            continue
        tot["orienta"] += 1

        nv = len(p.exterior.coords) - 1
        idx = set()
        for t in ti["testadas"]:
            idx.update(t.get("indices_arestas") or [])
        # cenário mais folgado possível: AF 3 m e lateral mínima (1,5 m).
        # Se NEM ASSIM sai envelope, o desenho está falhando — não é o lote
        # que é apertado.
        dists = [3.0 if i in idx else 1.5 for i in range(nv)]
        env = dl._offset_por_aresta(p, dists)
        if env is None:
            if len(falhas_exemplo) < 8:
                falhas_exemplo.append((nul, nv, round(poly.area, 1),
                                       round(100 * poly.area / poly.convex_hull.area, 1)))
            continue
        tot["envelope"] += 1
        tot["ok"] += 1

    print()
    base = tot["orienta"] or 1
    print(f"lotes localizados ............ {tot['lote']}")
    print(f"com testada identificada ..... {tot['testada']}")
    print(f"geometria complexa (3+ ruas).. {tot['complexa']}  (fora de escopo, aceito)")
    print(f"orientados p/ desenho ........ {tot['orienta']}  <- universo alvo")
    print(f"ENVELOPE OK (AF3 + lat1,5) ... {tot['envelope']}  = {100*tot['envelope']/base:.1f}%")
    if falhas_exemplo:
        print("\nexemplos de falha (nulotctm, vértices, área, % do hull):")
        for f in falhas_exemplo:
            print("   ", f)


if __name__ == "__main__":
    main()
