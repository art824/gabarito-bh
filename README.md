# Lote BH — consulta de parâmetros urbanísticos (Lei 11.181/19)

## O que já funciona (Fase 1 — motor de validação)
`python3 engine/consulta.py <lat> <lon>` devolve, para qualquer ponto de BH:
zoneamento (sigla + descrição), ADEs incidentes (inclusive sobrepostas),
via mais próxima com classificação e faixa de largura, coeficientes de
aproveitamento e quota (tabela 10 do Anexo XII), afastamento frontal pela
classe da via (tabela 3), regra geral de afastamentos laterais/AMD, e as
exceções de ADE que incidem no ponto — sempre com alertas explícitos do
que o sistema ainda NÃO verifica.

## Estrutura
```
lote-bh/
├── data/
│   ├── geo/        # shapefiles BHMAP (zoneamento, ADE, viária) — EPSG:31983
│   └── params/     # Anexo XII estruturado em JSON, com referência de origem
├── engine/consulta.py
├── docs/           # lei e anexo XII convertidos p/ texto
└── README.md
```

## Pendências de DADOS
1. ~~Camada TP (Anexo II)~~ INCORPORADA — TO/TP saem na ficha (02/07/26).
2. ~~Conexão fundo de vale / ADE Interesse Ambiental~~ INCORPORADAS.
3. **Setores internos de ADE (Anexo VII)** — ainda pendente; hoje vira alerta.
4. **Camadas de OUC e PVP (Anexo IV)** — ainda pendentes; hoje vira alerta.

## Pendências de REVISÃO (bloqueiam qualquer uso público)
- ~~Linhas VERIFICAR da tabela 10~~ COMPLETAS (dupla fonte: texto + print oficial).
- Revisão do Arthur via `docs/ficha_conferencia.html` (58 itens com checkbox).
- Caso-limite: via com largura exatamente 15 m (lei diz ">15", shapefile agrupa ">=15").

## Roteiro
- [x] Fase 0 — dados geográficos + lei estruturada (parcial: faltam camadas acima)
- [x] Fase 1 — motor de consulta ponto→ficha (v0 funcionando)
- [~] Fase 1.5 — geocodificação (endereço→lat/lon) + bateria de testes com
      lotes de resposta conhecida, validados por pessoas de confiança
- [ ] Fase 2 — site: landing + ficha + login + freemium (Supabase + Vercel)
- [ ] Fase 3 — "dúvida específica" com IA citando artigos da lei

## Avisos que o produto final DEVE exibir
Informação de apoio ao projeto; não substitui análise de responsável técnico
nem consulta oficial à PBH. Plano Diretor em processo de revisão — a base
legal pode mudar.
