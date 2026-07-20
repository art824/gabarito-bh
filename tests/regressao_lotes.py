# -*- coding: utf-8 -*-
"""
Bateria de regressão do motor contra lotes de RESPOSTA CONHECIDA (conferidos
no IBED oficial do SIURBE). Rodar antes de qualquer mudança no motor:

    python tests/regressao_lotes.py

Sai com código 1 se qualquer valor divergir — é o gate de confiança pedido
pela K2 ("conferir muito os dados; passar por muitos testes").

COMO ADICIONAR UM CASO: peça o IBED do lote no SIURBE, preencha um dict em
CASOS com o índice cadastral (preferível — não depende de rede/Mapbox) ou
lat/lon fixos, e os valores esperados copiados do IBED. Anote o número e a
data da solicitação do IBED no nome do caso (a lei muda; o IBED é um retrato).
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "engine"))

from consulta import carregar_camadas, consultar          # noqa: E402
from indice_cadastral import buscar_por_indice            # noqa: E402

CASOS = [
    {
        "nome": "Rua do Carmelo 93 — IBED 2295519 (21/10/2024)",
        "indice": "863004A004 0034",
        "esperado": {
            "zoneamento.sigla": "OP-1",
            "ficha.coef_aproveitamento.ca_bas": 1.0,
            "ficha.taxa_permeabilidade_min": "20%",
            "via_mais_proxima.classificacao": "LOCAL",
            "via_mais_proxima.faixa_largura": "10m <= LARGURA DA VIA < 15m",
            "ades": [],
        },
        # IBED declara 1000 m²; o CTM calcula do vetor do lote — tolerância 5%
        "area_ctm_aprox": (1000.0, 0.05),
    },
    {
        "nome": "Praça da Liberdade — logradouro público (zoneamento OP-3 + ADE Contorno)",
        "latlon": (-19.9319, -43.9377),
        "esperado": {
            "zoneamento.sigla": "OP-3",
            "ficha.coef_aproveitamento.ca_bas": 1.0,
            "ficha.coef_aproveitamento.ca_max": 5.0,
            "ficha.taxa_permeabilidade_min": "20%",
            "ficha.taxa_ocupacao_max": "80%",
            "ades": ["ADE Avenida do Contorno"],
            "via_mais_proxima.classificacao": "ARTERIAL",
        },
    },
]


def _pegar(d, caminho):
    """Navega 'a.b.c' em dicts aninhados; None-safe."""
    atual = d
    for parte in caminho.split("."):
        if atual is None:
            return None
        atual = atual.get(parte) if isinstance(atual, dict) else None
    return atual


def main():
    print("Carregando camadas...")
    ZON, ADE, VIA, EXTRAS = carregar_camadas()
    falhas = []

    for caso in CASOS:
        nome = caso["nome"]
        if "indice" in caso:
            g = buscar_por_indice(caso["indice"], EXTRAS.get("indice_cadastral"), EXTRAS.get("lote_ctm"))
            lat, lon = g["lat"], g["lon"]
        else:
            lat, lon = caso["latlon"]
        res = consultar(lat, lon, ZON, ADE, VIA, EXTRAS)

        for caminho, esperado in caso["esperado"].items():
            obtido = _pegar(res, caminho)
            ok = obtido == esperado
            status = "ok  " if ok else "FALHA"
            print(f"  [{status}] {nome} :: {caminho} = {obtido!r}" + ("" if ok else f" (esperado {esperado!r})"))
            if not ok:
                falhas.append((nome, caminho, esperado, obtido))

        if "area_ctm_aprox" in caso:
            alvo, tol = caso["area_ctm_aprox"]
            area = (res.get("lote_real") or {}).get("area_m2")
            ok = area is not None and abs(area - alvo) / alvo <= tol
            status = "ok  " if ok else "FALHA"
            print(f"  [{status}] {nome} :: area_ctm ≈ {alvo:g} m² (±{tol:.0%}) = {area!r}")
            if not ok:
                falhas.append((nome, "area_ctm", alvo, area))

    print()
    if falhas:
        print(f"REGRESSÃO: {len(falhas)} divergência(s). NÃO publicar sem investigar.")
        sys.exit(1)
    print(f"Regressão ok — {len(CASOS)} lote(s), todas as verificações bateram.")


if __name__ == "__main__":
    main()
