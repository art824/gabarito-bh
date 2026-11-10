"""Gera as fichas de EXEMPLO da página /exemplos (foto de uma data).

Roda a própria ferramenta (rota /consulta) para alguns lotes públicos e grava o
texto das seções da ficha em webapp/templates/_exemplos_fichas.html. A página
/exemplos só lê esse arquivo: não consulta o CINDACTA nem o Mapbox a cada visita.

Por quê: assistentes de IA e buscadores não preenchem formulário, então não
enxergam o que a ficha mostra. A vitrine mostra TUDO que a ficha entrega, de
lotes reais, sem permitir que a IA consulte o lote de ninguém (para isso a
pessoa precisa entrar no site).

Uso (na pasta lote-bh, com o .env do Mapbox):  python scripts/gerar_exemplos.py
Refazer quando a base de dados ou a lei mudarem (a data sai na página).
Cada execução faz 1 geocodificação (Mapbox) e 1 consulta ao CINDACTA por exemplo.
"""
import html
import os
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "webapp"))
sys.path.insert(0, str(RAIZ / "engine"))
os.chdir(RAIZ / "webapp")

import app as A  # noqa: E402  (carrega as camadas; leva alguns segundos)

# Lotes públicos/institucionais e de zoneamentos diferentes. Só o endereço aparece
# na página (a ficha não traz nome de proprietário).
EXEMPLOS = [
    ("Rua Paraíba, 697, Belo Horizonte", "savassi"),
    ("Avenida Otacílio Negrão de Lima, 3000, Belo Horizonte", "pampulha"),
    ("Rua Pitangui, 3230, Belo Horizonte", "horto"),
]


def _limpar(frag: str) -> str:
    frag = re.sub(r"<script.*?</script>", "", frag, flags=re.S)
    frag = re.sub(r"<svg.*?</svg>", "", frag, flags=re.S)
    frag = re.sub(r"<button.*?</button>", "", frag, flags=re.S)
    # links internos para âncoras que não existem na vitrine viram texto
    frag = re.sub(r'<a [^>]*href="#[^"]*"[^>]*>(.*?)</a>', r"\1", frag, flags=re.S)
    # links para a própria ferramenta (dxf, consulta) saem: a vitrine não consulta
    frag = re.sub(r'<a [^>]*href="/consulta[^"]*"[^>]*>(.*?)</a>', r"\1", frag, flags=re.S)
    frag = frag.replace("Calcular no estudo ↓", "Calculado no estudo interativo do site")
    frag = re.sub(r'\sid="[^"]*"', "", frag)  # ids repetiriam entre exemplos
    frag = re.sub(r'\sdata-[a-z-]+="[^"]*"', "", frag)
    return frag


def _texto(frag: str) -> str:
    t = re.sub(r"<[^>]+>", " ", frag)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def gerar_um(client, endereco: str, slug: str) -> str:
    t = client.post("/consulta", data={"modo": "endereco", "endereco": endereco}).get_data(as_text=True)
    secoes = [m.group(0) for m in re.finditer(r'<section class="fsec[^"]*"[^>]*>.*?</section>', t, flags=re.S)
              if "fsec-estudo" not in m.group(0)[:60]]
    if len(secoes) < 4:
        raise SystemExit(f"Ficha incompleta para {endereco!r} ({len(secoes)} seções)")
    confirmado = re.search(r"Endereço confirmado: <b>([^<]*)</b>", t)
    zon = re.search(r"Zoneamento</span>.*?<span class=\"v[^\"]*\"[^>]*>\s*([^<\n]+)", t, flags=re.S)
    alertas = re.search(r'<details class="bloco-alertas.*?</details>', t, flags=re.S)
    fontes = re.search(r'<details class="bloco-fontes.*?</details>', t, flags=re.S)
    titulo = confirmado.group(1).split(",")[0:2] if confirmado else [endereco]
    titulo = ", ".join(x.strip() for x in titulo)
    partes = [_limpar(s) for s in secoes]
    if alertas:
        partes.append(_limpar(alertas.group(0)).replace("<details ", "<details open ", 1))
    if fontes:
        partes.append(_limpar(fontes.group(0)))
    corpo = "\n".join(partes)
    resumo = f"zoneamento {_texto(zon.group(1))}" if zon else ""
    return (
        f'<article class="ficha ficha-exemplo" aria-labelledby="ex-{slug}">\n'
        f'  <h2 id="ex-{slug}" class="ex-titulo">{html.escape(titulo)}'
        f'{(" · " + html.escape(resumo)) if resumo else ""}</h2>\n'
        f"{corpo}\n</article>\n"
    )


def main():
    client = A.app.test_client()
    blocos = []
    for endereco, slug in EXEMPLOS:
        print("gerando:", endereco, flush=True)
        blocos.append(gerar_um(client, endereco, slug))
    saida = RAIZ / "webapp" / "templates" / "_exemplos_fichas.html"
    saida.write_text(
        "{# GERADO por scripts/gerar_exemplos.py em %s. Não editar à mão. #}\n" % date.today().isoformat()
        + "\n".join(blocos),
        encoding="utf-8",
    )
    print("gravado:", saida, f"({saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
