# Plano de ação — Gabarito (atualizado 20/07/2026)

Origem: entrevistas com K2 Arquitetura (mercado/profissional) e Soluz
(estudante), mais decisões tomadas com o Arthur ao longo do deploy.
Princípio que atravessa tudo, dito pela K2: **confiabilidade antes de
feature** — "melhor mostrar 'indisponível' do que informação errada".

---

## ✅ JÁ ESTÁ NO AR (feito em 07/2026)

**Infraestrutura**
- Site no ar em `gabarito-bh.onrender.com` (Render free), deploy automático
  a cada push no GitHub (`art824/gabarito-bh`).
- Keep-alive por cron-job.org (GET a cada 10 min) — evita o cold-start de
  30-60s do plano grátis. UptimeRobot avisa se cair.
- Google Analytics (G-DKFJ0FHDN6) medindo visitas + eventos próprios
  (consulta visualizada, slider de altura, exportar PDF, reportar desenho).
- RAM do processo caiu de ~800-900MB para ~270MB (migração pra DuckDB), que
  é o que viabiliza hospedar de graça.

**Fase 1 — Confiança**
- Bug do índice cadastral corrigido (mostrava a unidade errada em lote com
  várias economias — era o caso do IBED da Rua do Carmelo).
- Falha honesta no anexo interativo: em vez de desenho duvidoso, aviso de
  indisponibilidade + estudo genérico editável.
- Bateria de regressão (`python tests/regressao_lotes.py`) com 3 lotes de
  resposta conhecida — roda antes de publicar mudança no motor.

**Fase 2 — Transparência**
- Fonte de cada dado, agrupada por bloco num botão "De onde vêm estes dados?".
- Edificação: quando não há registro, diz isso explicitamente (não some).
- Veredito "Pode construir" verde no topo da ficha, com o detalhe do que foi
  e do que não foi verificado.

**Fase 3 — Produto**
- Lotes de esquina: as 2 ruas com igual destaque, cada uma com seu AF.
- Potencial construtivo: gráfico comparando CA básico × máximo (mostra
  quantas vezes maior), com m² e unidades quando o lote é identificado.
- PDF diagramado (print CSS dedicado, cabeçalho com data de emissão, fontes
  expandidas automaticamente na impressão).

---

## 🔜 DAQUI PRA FRENTE — em ordem de prioridade

### 1. CINDACTA / altura de aeródromo — **FEITO (21-22/07/2026)**
Não existe camada baixável das superfícies clássicas do aeródromo — testado
exaustivamente nos dois portais WFS/WMS da PBH. A solução real: a PBH
mantém `BHMAP_ALTIMETRIA` (WFS, consultada ao vivo por ponto, ver
`engine/cindacta.py`), com o histórico da altura já liberada por lote pelo
CINDACTA. Implementado: bloco na ficha com valor atual + anterior (com
aviso de que a IBED pode estar desatualizada), e o veredito "pode
construir" só vira "não" quando a altura liberada é ≤ 3m. Detalhes técnicos
completos e as armadilhas encontradas estão no CLAUDE.md.
**Pendente:** usar esse valor como teto do slider de altura no anexo
interativo (item (d) do plano original) — ainda não feito.

### 2. Fechar as pontas do que já está no ar
- **Domínio próprio** (`gabaritoarq.com.br`): DNS configurado no Registro.br,
  aguardando propagação/certificado no Render. Conferir e, quando funcionar,
  trocar o link divulgado.
- **Bug real pendente:** o botão "reportar desenho" grava em arquivo local
  (`data/relatos_desenho.jsonl`), e o disco do Render free é **apagado a cada
  deploy** — relatos de usuários reais estão sendo perdidos em silêncio.
  Precisa mandar para um destino persistente (e-mail, planilha ou banco).
- **Validar o PDF**: Arthur precisa abrir a ficha, dar Ctrl+P e conferir se a
  diagramação ficou digna do que será o recurso pago.
- **Backup do `data/geo/`** (~1,6GB): só existe no PC do Arthur. Copiar pra
  HD externo/nuvem — é o único item insubstituível sem retrabalho.

### 3. Ampliar a bateria de regressão (contínuo)
A cada IBED que o Arthur trouxer, virar um caso novo no
`tests/regressao_lotes.py`. É o que impede uma mudança futura de quebrar
silenciosamente um dado certo. Barato de fazer, alto retorno de confiança.

### 4. Fase 5 — dados novos
- **APP / meio ambiente, patrimônio cultural, TCU** — a K2 disse que agregam
  bastante e já aparecem no IBED. Verificar disponibilidade no BHMAP (o
  patrimônio provavelmente é da DPCA-FMC, outro sistema) e integrar no mesmo
  padrão: `preparar_dados.py` → ficha com origem.
- **DWG por zona** (pedido da Soluz): investigar onde a PBH publica os DWGs.
  Mínimo viável: dizer NA FICHA em que zona o lote está; ideal: link direto.

### 5. Melhorias de motor conhecidas (quando incomodarem)
- Lotes muito irregulares (ex. Fernandes Tourinho 200) caem em "inconstruível"
  em toda altura — não sabemos ainda se é limitação real da geometria ou do
  algoritmo de recuo por aresta. Hoje é honesto (avisa), mas dá pra melhorar.
- Resolução item-a-item das regras por setor de ADE (Anexo VII) — hoje o site
  mostra o nome do setor, mas não aplica a regra específica dele.
- Lotes com 3+ ruas continuam em "geometria complexa" → modo manual.

### 6. Distribuição e validação (com o Arthur, fora do código)
- Olhar o Google Analytics em 2-4 semanas: quantas consultas de verdade, quem
  volta. **Sem esse número, qualquer conta de monetização é chute.**
- Acadêmico: UFMG (Next / iniciação científica), prof. Tiago Castelo Branco
  (UFMG e PUC), apresentar numa amostra de arquitetura da PUC. O conceito do
  gabarito "já é um TCC" segundo a K2.
- Continuar coletando feedback de escritórios (o retorno da K2 pagou sozinho
  duas fases deste plano).

### 7. Monetização — **adiada por decisão consciente**
- Google AdSense: DESCARTADO por ora. RPM no Brasil é baixo (~R$ 2-8 por mil
  páginas) e anúncio genérico ao lado de uma ficha técnica mancha a
  credibilidade, que é o ativo nº 1 do produto.
- Caminho escolhido para o médio/longo prazo: **patrocínio direto de
  imobiliárias/incorporadoras de BH** (rende mais, anúncio relevante, Arthur
  controla o que aparece) + **PDF pago** (por isso a diagramação já foi feita).
- **Política de Privacidade**: adiada, mas é devida por causa do Analytics e
  seria pré-requisito de qualquer anúncio. Fazer quando a monetização voltar
  à mesa (ou antes, se o tráfego crescer).

---

## Como o trabalho anda
Regra que vale pra tudo acima: mudança no motor só entra depois de passar na
bateria de regressão, e todo dado novo na ficha nasce com sua fonte declarada.
