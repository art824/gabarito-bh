# Gabarito — parâmetros urbanísticos de Belo Horizonte

Site: https://gabaritoarq.com.br · Ferramenta grátis, sem cadastro.

O usuário digita um endereço ou índice cadastral e recebe a ficha urbanística do lote pela
Lei 11.181/19 (Plano Diretor): zoneamento, ADEs, via, coeficientes de aproveitamento, quota,
afastamentos, taxas de ocupação e permeabilidade, proteção cultural, altura máxima do CINDACTA,
construção existente, um estudo interativo do volume construível e exportação DXF para CAD.
Cada dado mostra a sua fonte, e a ficha lista o que NÃO verifica.

> Apoio ao estudo preliminar. Não substitui um responsável técnico nem a consulta oficial à
> Prefeitura de Belo Horizonte. O Plano Diretor está em revisão: a base legal pode mudar.

## Rodar local
```
pip install -r requirements.txt
python scripts/preparar_dados.py      # gera os caches a partir dos CSV/shapes do BHMap (data/geo)
python webapp/app.py                  # http://localhost:5000
python tests/regressao_lotes.py       # rodar antes de publicar mudança no motor
```
Precisa de `MAPBOX_TOKEN` em um arquivo `.env` (não versionado) para buscar por endereço.
Os dados pesados (`data/geo/`, 1,5 GB) não estão no repositório.

## Como é publicado
- **Código:** push na `master` faz deploy automático no Render (plano grátis, 512 MB de RAM).
- **Dados pesados:** o arquivo `dados_producao.zip` fica na release `dados-v1` deste repositório e
  o Render o baixa a cada deploy. Trocar esse arquivo é manual: refazer o zip do zero, testar a
  integridade e manter o mesmo nome.
- **Camadas pequenas** (proteção cultural) vão no próprio Git em `data/camadas_extra/`.
- **Saúde:** `/saude` mostra quais camadas de dados o servidor carregou. Camada ausente faz a ficha
  dizer "Não verificado" (nunca "Não").
- **Verificação automática:** o GitHub Actions (`.github/workflows/verificar.yml`) confere sintaxe,
  templates, JSONs, vazamento de segredos e vulnerabilidades das dependências a cada push.

## Mais informação
- `CLAUDE.md` — regras do projeto, arquitetura, armadilhas e deploy (para quem for mexer).
- `docs/historico_decisoes.md` — histórico detalhado de decisões e bugs.
- `docs/visao_e_plano.md` — para onde o produto vai, em fases.
- `data/params/` — tabelas do Anexo XII em JSON, com a origem de cada valor.
- Privacidade: https://gabaritoarq.com.br/privacidade
