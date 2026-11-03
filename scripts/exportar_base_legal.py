# -*- coding: utf-8 -*-
"""
Exporta, da base de legislação de BH (repositório PRIVADO, somente leitura),
só os artigos da Lei 11.181/2019 que o Gabarito cita na ficha, para
`data/params/base_legal.json` (arquivo pequeno, que vai junto com o site).

O site NUNCA lê a base privada em tempo de execução: ele lê só este JSON. Se o
arquivo faltar ou estiver quebrado, a ficha simplesmente não mostra o bloco
"Base legal" (ver `_carregar_base_legal` em webapp/app.py).

Uso:
    python scripts/exportar_base_legal.py
    python scripts/exportar_base_legal.py "C:/caminho/da/base"

Rodar de novo sempre que a base avisar que um desses artigos mudou. O texto vem
do LegisWeb (consolidação NÃO oficial); as "Notas Legisweb" são descartadas.
"""
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE_PADRAO = Path("C:/claude sites/Programas arq automatico/Informações - legislação arquitetônica")
LEI = "lei-11181-2019"
# Artigos que a ficha cita: 158 (parâmetros que todo projeto deve observar),
# 161 (taxa de permeabilidade) e 115 (afastamento frontal e recuo de alinhamento).
ARTIGOS = ["158", "161", "115"]
SAIDA = RAIZ / "data" / "params" / "base_legal.json"


def _limpar(texto: str) -> str:
    texto = re.sub(r"\s*Nota Legisweb:.*", "", texto, flags=re.S)
    return re.sub(r"[ \t]+", " ", texto).strip()


def main() -> int:
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("BASE_LEGISLACAO", BASE_PADRAO))
    lei = json.loads((base / "estruturado" / f"{LEI}.json").read_text(encoding="utf-8"))
    fontes = json.loads((base / "fontes.json").read_text(encoding="utf-8"))
    fonte = next(f for f in fontes["fontes"] if f["id"] == LEI)

    artigos = []
    for numero in ARTIGOS:
        a = next((x for x in lei["artigos"] if x["artigo"] == numero), None)
        if a is None:
            raise SystemExit(f"Artigo {numero} não existe na base: {LEI}")
        linhas = []
        for d in a["dispositivos"]:
            t = _limpar(d["texto"])
            linhas.append(f"Art. {numero} {t}" if d.get("tipo") == "caput" else t)
        artigos.append({
            "artigo": numero,
            "local": " · ".join(v for v in a["hierarquia"].values() if v),
            "situacao": a["situacao"],
            "alterado": bool(a["alteracoes"]),
            "linhas": linhas,
            "sha256": a["sha256"],
        })

    saida = {
        "lei": "Lei 11.181/2019 (Plano Diretor de Belo Horizonte)",
        "fonte": "LegisWeb (consolidação não oficial)",
        "url_oficial": fonte.get("oficial"),
        "verificado_em": fonte["verificado_em"],
        "sha256_lei": fonte["sha256_texto"],
        "aviso": ("Texto de referência, não substitui o texto oficial. "
                  "Situação 'vigente' quer dizer que o artigo não foi revogado no texto consolidado."),
        "artigos": artigos,
    }
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"gravado: {SAIDA} ({SAIDA.stat().st_size} bytes, {len(artigos)} artigos, verificado em {saida['verificado_em']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
