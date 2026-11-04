# CLAUDE.md — Gabarito (gabaritoarq.com.br)

Ferramenta grátis: o usuário digita um endereço (ou índice cadastral) de Belo Horizonte e recebe a
ficha urbanística do lote pela Lei 11.181/19 (Plano Diretor): zoneamento, ADEs, via, coeficientes
(CA), quota, afastamentos, TO/TP, proteção cultural, altura do CINDACTA, construção existente,
estudo interativo do volume construível e exportação DXF para CAD.

**Histórico completo, decisões e armadilhas:** `docs/historico_decisoes.md` (use busca; é longo).
**Direção e plano em fases:** `docs/visao_e_plano.md`. Ler os dois antes de planejar algo grande.

## Quem é o usuário
Arthur, estudante de Arquitetura e Urbanismo (UFMG). Sem experiência com backend: explique
infraestrutura (banco, deploy, login) passo a passo e o porquê. Prefere mudanças cirúrgicas
(nunca reescrever arquivo inteiro sem pedido). Falar em português. Questioná-lo quando houver base
factual. Quer que o resultado seja verificado onde o efeito importa (ex.: no site publicado), não
só que o comando tenha rodado.

## Regras inegociáveis
- **Ética do produto:** é informação para decisão de projeto real. A ficha sempre mostra que não
  substitui responsável técnico nem a consulta oficial; lista o que NÃO verifica; avisa que o
  Plano Diretor está em revisão. **Camada de dado ausente = "Não verificado", nunca "Não"**
  (bug real de 03/11/2026: ver `docs/historico_decisoes.md` e `/saude`).
- A ficha é determinística (geo + tabelas), sem LLM. Exceções de ADE nunca são silenciosas.
- Todo campo novo da ficha tem fonte indicada (bloco "Fontes dos dados").
- **O repositório é PÚBLICO.** Nunca commitar: `.env`/tokens, dados pessoais, nomes/condições de
  terceiros (ex.: contato institucional), notas estratégicas. Esses ficam em notas privadas
  fora do repo. Antes de `git push`, conferir `git diff origin/master`.
- Publicar só o que mudou: criar worktree a partir de `origin/master`, copiar os arquivos,
  commitar e `git push origin HEAD:master`; depois alinhar o local com `git rebase origin/master`.

## Arquitetura
```
engine/consulta.py    motor: lat/lon -> ficha (camadas, exceções de ADE, testadas, proteção)
engine/desenho_lote.py envelope construtivo (recuo por aresta = lote menos buffers), TP, mancha
engine/db_lotes.py    consulta indexada em disco (DuckDB + RTREE): lotes, IPTU, edificação
engine/cindacta.py    altura máxima por aeródromo, WFS ao vivo da PBH (cache 6 h, freio 30/min)
engine/dxf_lote.py    exporta o estudo para DXF em UTM real
engine/geocode.py     endereço -> lat/lon (Mapbox); indice_cadastral.py busca direta por índice
webapp/app.py         Flask: /, /consulta, /consulta/estudo, /consulta/dxf, /reportar,
                      /privacidade, /saude, robots/sitemap; cabeçalhos de segurança e limites
webapp/templates, static  páginas, style.css, script.js, fonts/ (hospedadas aqui)
data/params/          Anexo XII em JSON (ca_quota, afastamentos_alturas) + base_legal.json
data/camadas_extra/   camadas pequenas versionadas (proteção cultural) usadas como reserva
data/geo/             shapefiles e cache do BHMap: NÃO versionado (1,5 GB), só local
tests/                regressao_lotes.py (4 lotes IBED), cobertura_anexo.py, diag_anexo.py
```

## Comandos
```
pip install -r requirements.txt
python scripts/preparar_dados.py            # após CSV/shape novo: gera Parquet e .duckdb
python webapp/app.py                        # site local em localhost:5000 (launch.json: "webapp")
python tests/regressao_lotes.py             # RODAR antes de publicar qualquer mudança no motor
python scripts/exportar_base_legal.py       # regenera data/params/base_legal.json (lê a base de leis)
```
Token Mapbox em `.env` (`MAPBOX_TOKEN=...`), nunca versionado.

## Deploy e dados (Render grátis, 512 MB de RAM)
- Código: push na `master` de `art824/gabarito-bh` faz deploy automático (~2-3 min).
- Dados pesados: `dados_producao.zip` na RELEASE `dados-v1` do GitHub; o Render baixa a cada
  deploy. Trocar o arquivo é manual (não há `gh` instalado). Refazer o zip DO ZERO e rodar
  `testzip()`; mesmo nome de arquivo para a URL não mudar.
- **O zip de produção NÃO tem a APP** (`APP.parquet`, ~+45 MB de RAM: arriscaria passar de 512 MB).
  A proteção cultural vem de `data/camadas_extra/`. Conferir sempre `/saude` depois do deploy:
  `ausentes` lista as camadas que faltam e a ficha diz "Não verificado" para elas.
- Limite grátis: 750 h/mês; instância dorme (cold start ~50 s).
- Memória é o ponto frágil: ~457 MB após 3 fichas. Qualquer camada nova ou rota pesada
  exige medir RAM antes de publicar.

## Armadilhas que já custaram caro (resumo; detalhes no histórico)
- `shapely.distance` em laço com `gpd.read_file(bbox=)` mata o processo: usar DuckDB espacial.
- Nunca "consertar" geometria inválida com `buffer(0)` sem checar o que ela virou.
- CSS: classe com `display` vence o atributo `hidden`; variável CSS não definida falha em silêncio.
- `NULOTCTM` deve ser lido como string (zero à esquerda).
- RTREE do DuckDB exige coluna `GEOMETRY` pura.
- O preview do Claude Code reporta `prefers-reduced-motion: reduce` sempre; não esconder
  conteúdo atrás de animação sem fallback.
- `consultar()` é rechamado a cada arrastada do slider: nada de consulta de rede dentro dele.

## Estado e pendências
Ver `docs/visao_e_plano.md` (fases) e as notas privadas do Arthur. Pontos técnicos abertos:
ligar a APP (exige plano pago ou camada menor), limite por IP nas rotas pesadas, legendas
dos termos técnicos na ficha, Anexo XII dentro da base de legislação, versão pensada para celular.
