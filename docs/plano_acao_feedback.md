# Plano de ação — feedback K2 + Soluz (07/2026)

Origem: entrevistas com K2 Arquitetura (mercado/profissional) e Soluz
(estudante). Princípio que atravessa tudo, dito pela K2: **confiabilidade
antes de feature** — "melhor mostrar 'indisponível' do que informação errada".

> STATUS: Fases 1, 2 e 3 EXECUTADAS em 20/07/2026 (detalhes no CLAUDE.md).
> Próxima: Fase 4 (CINDACTA — aguardando dados do Arthur; estrutura já
> vista no IBED 2295519). Fase 5 (dados novos + DWG por zona) e Fase 6
> (acadêmico/monetização) seguem pendentes.

## Fase 1 — Confiança (bugs que queimam o site) — FEITA
1. **Bug do índice cadastral** (2 últimos dígitos divergem entre o que o
   site devolve e o que a informação básica dá). Arthur tem exemplo
   concreto — reproduzir com ele. Hipótese inicial: os 2 últimos dígitos
   são o sequencial da unidade/economia (lote com várias economias tem
   vários índices; podemos estar exibindo o primeiro registro em vez do
   consultado). Grave: arquiteto que percebe isso não volta.
2. **Anexo interativo — política de falha honesta**: quando a geometria é
   complexa/suspeita (esquina não resolvida, offset falhou, resultado
   duvidoso), exibir "anexo indisponível para este lote" em vez de desenho
   possivelmente errado. Mapear os estados atuais de erro silencioso.
3. **Bateria de regressão com lotes reais**: script que roda N lotes de
   resposta conhecida (conferidos contra a informação básica do SIURBE) e
   acusa divergência. Vira gate pra qualquer mudança futura no motor.

## Fase 2 — Transparência (origem de cada dado) — FEITA
4. **Origem por campo na ficha**: cada dado com fonte (camada BHMAP /
   IPTU / derivado) — pode ser tooltip/ícone pequeno pra não poluir.
5. **Data da edificação**: mostrar a origem; quando NÃO há registro,
   disclaimer explícito: "sem registro na base a que temos acesso — pode
   existir edificação não registrada; conferir". Nunca inventar dado.
   (Já houve caso de edificação errada apontado pela K2.)
6. **Veredito "pode construir?" no topo da ficha** (pedido pensando em
   corretores): logo após um scroll, resposta direta "pode construir" /
   "não pode construir por X", sempre com a origem da informação.

## Fase 3 — Produto (quick wins pedidos) — FEITA
7. **Lotes de esquina**: as DUAS ruas com igual destaque na ficha (hoje a
   segunda fica como "provável", de canto) e no anexo interativo; quando
   não der pra desenhar direito, disclaimer em vez de desenho errado.
8. **Calculadora de CA dentro da consulta**: o anexo da landing
   (potencial construtivo) replicado na página de consulta, com o
   zoneamento já preenchido pelo lote consultado, mantendo o slider de
   área. K2: "é o que os corretores mais querem ver".
9. **PDF diagramado de verdade** (item do Arthur, não das entrevistas):
   hoje o export é um `window.print()` com CSS de impressão — funciona,
   mas não tem cara de documento que vale dinheiro. Redesenhar o PDF como
   peça diagramada (layout de prancha/relatório profissional: capa ou
   cabeçalho com identificação do lote, ficha organizada, anexo/desenho,
   carimbo, fontes e disclaimers) — é o que justifica ele virar o recurso
   PAGO já decidido pra fase de monetização. Avaliar gerar server-side
   (ex. WeasyPrint) vs. melhorar o print CSS ao limite.

## Fase 4 — CINDACTA (começa JÁ, em paralelo — Arthur pilotando os dados)
9. "Make or break" segundo a K2: altura máxima da aeronáutica
   desclassifica muitos lotes e quase ninguém em BH sabe calcular.
   Arthur vai enviar os dados e explicar o funcionamento nos próximos
   dias. Passos: (a) receber/entender os dados DECEA com Arthur,
   (b) estudo de viabilidade (formato, cobertura, cruzamento espacial),
   (c) integrar altura máxima na ficha com origem e disclaimers.

## Fase 5 — Dados novos do BHMAP
10. APP / meio ambiente, patrimônio histórico, TCU — verificar
    disponibilidade das camadas no BHMAP e integrar (mesmo padrão das
    camadas atuais: preparar_dados.py → ficha com origem).
11. **DWG por zona** (pedido da Soluz): investigar onde a PBH publica os
    DWGs por zona. Mínimo viável: indicar NA FICHA em qual zona o lote
    está; ideal: link direto (ou download) do DWG da zona.

## Fase 6 — Fora de código (fica com Arthur)
- Acadêmico: UFMG (Next/iniciação científica), prof. Tiago Castelo Branco
  (UFMG/PUC), amostra de arquitetura da PUC. O conceito "já é um TCC".
- Monetização (pop-up de propaganda, venda pra imobiliárias): DECIDIDO
  ficar FORA por enquanto — só depois do site validado e com fluxo.

## Ordem de execução combinada
Fase 1 → 2 → 3 sequencial (confiança primeiro); Fase 4 (CINDACTA) corre
em paralelo desde já, no ritmo dos dados que o Arthur enviar; Fase 5
depois da 3; Fase 6 é do Arthur.
