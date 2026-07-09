# CLAUDE.md — Lote BH (consulta de parâmetros urbanísticos, Lei 11.181/19)

## Quem é o usuário
Arthur, estudante de arquitetura e urbanismo em Belo Horizonte. Sem experiência
com backend — TODA etapa de infraestrutura (banco, login, deploy) precisa ser
guiada passo a passo, explicando o porquê. Ele prefere mudanças cirúrgicas:
nunca reescrever arquivos inteiros sem pedido explícito. Falar em português.
Questionar decisões dele quando houver base factual — ele pediu isso
explicitamente; não concordar automaticamente.

## O que é o projeto
SaaS local para BH: o usuário digita um endereço e recebe a "ficha urbanística"
do lote — zoneamento, ADEs incidentes, via e classificação, coeficiente de
aproveitamento (CAmin/bas/max/cent), quota de terreno, afastamento frontal,
afastamentos laterais/AMD (regra geral), TP mínima e TO máxima, e as exceções
de ADE que prevalecem sobre a regra geral.

Referência de mercado: OSPA Place (ospa.place) faz isso em POA/Floripa/etc.
BH não é coberta por ninguém (verificado em 07/2026) — essa é a tese do produto.
Decisão consciente: MVP SEM mapa interativo na home — só campo de endereço →
ficha.

DECISÃO DE MONETIZAÇÃO (07/2026, revista): NÃO vai ter paywall/freemium na v1.
Site 100% aberto (todas as consultas, sem limite), com QR/Pix de doação
("gostou? um cafezinho ajuda a manter o Gabarito no ar") + popup depois de
alguns segundos de uso. Motivo duplo: (a) modelo travado exigiria saber que é
"a mesma pessoa voltando" — login ou fingerprint/cookie com contagem no
backend, exatamente a complexidade que Arthur quer adiar; (b) a tese de
distribuição é virar hábito diário de estudante/arquiteto — fricção de
paywall mata isso. Monetização em camadas fica pra DEPOIS, sem travar a
consulta unitária: PDF exportável, acesso em lote/API pra escritórios, avisos
de mudança de lei.

## Estado atual (fim da fase de chat, 07/2026)
- FEITO: shapefiles do BHMAP integrados (EPSG:31983): zoneamento (1.715 pol.),
  ADE (25), classificação viária (~440k trechos), taxa de permeabilidade
  (1.715, espelha o zoneamento), conexão fundo de vale (74), ADE Interesse
  Ambiental (194). Conexão verde baixada mas ainda não usada.
- FEITO: Anexo XII estruturado em `data/params/*.json` — tabela 10 (CA/quota)
  COMPLETA para todas as 17 siglas, confirmada por dupla fonte (texto convertido
  + print do doc oficial). Tabelas 3, 4, 5, 11 e 12 estruturadas.
- FEITO: motor `engine/consulta.py` — lat/lon → ficha, com exceções de ADE
  aplicadas de forma NUNCA silenciosa (sempre exibidas) e alertas explícitos
  do que não é verificado. Testado: Praça da Liberdade (OP-3, ADE Contorno,
  TP20/TO80), orla Pampulha (PA-1, dupla ADE, TP95/TO3), Buritis.
- FEITO (07/2026): ambiente Windows configurado (Python 3.12 + geopandas nativos,
  sem WSL) — sessão anterior rodava em sandbox Linux do chat, que não persiste.
- FEITO: geocodificação via Mapbox (`engine/geocode.py`), token em `.env` (fora
  do versionamento). `engine/consulta.py --endereco "..."` funciona ponta a
  ponta. Arthur revisou `docs/ficha_conferencia.html` por olho (checkboxes não
  persistem, é normal) e não achou divergência.
- DECISÃO (07/2026): Arthur pulou a bateria formal de endereços por CLI — prefere
  validar direto na interface (digitar endereço, ver ficha, avaliar visualmente)
  assim que houver site. Motor não foi validado contra fonte externa independente
  ainda; ficha deve deixar isso claro até essa validação acontecer.
- FEITO (07/2026): site mínimo local (`webapp/`, Flask) só pra validação
  interativa — SEM login/banco/deploy, isso ainda é a Fase 2 de verdade.
  Testado no navegador: Praça da Liberdade (bate), Pampulha (dupla ADE +
  exceções + alertas de setor, tudo exibido). Corrigido bug de exibição
  "obs: nan" quando a camada de TP não tem mensagem (NaN do pandas sendo
  tratado como string válida) — `engine/consulta.py`.
- FEITO (07/2026): frontend "de produto" — nome definido: **Gabarito**
  (gabarito = limite de altura + "resposta certa"; subtítulo explicativo no
  hero). Landing (`templates/landing.html`) + página de consulta
  (`templates/consulta.html`) sobre `base.html` + `static/style.css`.
  Identidade v2 "PRANCHA" (07/2026, a pedido do Arthur — "algo arrojado, não
  só texto"): linguagem de desenho técnico de arquitetura — papel milimetrado
  (grid CSS no body), moldura de prancha fixa na viewport, SVG de implantação
  esquemática no hero (cotas, hachura, norte, chamada de detalhe), faixa
  escura com itens numerados 01–08, círculos de chamada de detalhe nos passos,
  seção "Notas gerais", ficha com CARIMBO de prancha (coordenadas em mono),
  exceções com borda terracota 10px, alertas em borda tracejada, footer em
  formato de carimbo. Fontes: Fraunces + Archivo + IBM Plex Mono. Paleta:
  papel #F2EDE0, tinta #14202C, terracota #B0402C. Botões com sombra dura
  terracota (efeito carimbo). Tab "Índice cadastral" na consulta segue
  desabilitada ("em breve"), esperando o shape CADASTRO_IPTU_IND_CADASTRAL.
- FEITO (07/2026) v2.1 "vida": `static/script.js` (vanilla, sem libs) —
  (a) prancha do hero se desenha como plotter (stroke-dasharray + pathLength,
  classes .traco/.anota com delays); (b) faixa de stats com contagem animada
  (números REAIS do banco: 1.715 zoneamentos, 25 ADEs, 440 mil vias, 410
  artigos); (c) calculadora interativa de potencial construtivo (slider área
  × zona OP-3/OP-2/OM-2/PA-3 → m² CAbas/CAmax + perfil SVG animado) — valores
  de CA reais da tabela 10; (d) placeholder digitando endereços reais;
  (e) reveals no scroll. Acessibilidade: prefers-reduced-motion desliga tudo.
  IMPORTANTE: o renderer do preview do Claude Code não dispara
  IntersectionObserver nem screenshots (sem frames) — por isso o script tem
  sonda de IO + fallback de 2,5s que ativa tudo se o observer estiver morto.
  Nunca esconder conteúdo atrás de animação sem esse fallback.
- FEITO (07/2026) v2.2 pós-brainstorm com Arthur (ele achou a prancha one-shot
  sem sentido; pediu movimento contínuo): (a) HERO VIVO — prancha estática
  substituída por mapa com contorno REAL de BH (dissolve do zoneamento via
  geopandas, script scratchpad gera_mapa_hero.py → templates/_mapa_bh.html) e
  pings em loop infinito (8 bairros, sigla+CA reais do motor, mini-card estilo
  carimbo); (b) FICHA VIVA — bloco "Anexo interativo — estudo rápido" na
  consulta: planta esquemática parametrizada com AF real (exceção de ADE
  numérica prevalece e ganha asterisco+nota), TP/TO e via reais + calculadora
  com CA/quota reais da ficha (área → potencial bas/max + unidades pela
  quota). Dados passam por app.py:_montar_estudo() ANTES da conversão de
  exceções p/ texto. Lição: Arthur usava Dark Reader e via cores invertidas —
  se ele reclamar de cor, perguntar da extensão primeiro.
- FEITO (07/2026) v2.3, feedback do Arthur sobre o estudo interativo:
  (a) FATOR B da fórmula do afastamento lateral (t.4) CONFIRMADO no .doc
  oficial (bytes UTF-16 desalinhados, decodificado por pares invertidos):
  B=8 em CR/AGEE/AGEUC/OP-3; B=6 centralidade local; B=4 demais. Camada de
  centralidades NÃO obtida → usamos B=4 fora das siglas B=8 (conservador,
  afastamento maior) com nota na interface. Registrado no JSON de params.
  (b) Estudo da ficha v2: inputs viraram TESTADA × PROFUNDIDADE (área é
  derivada — Arthur apontou que área é output, não input; quando o shape do
  IPTU chegar, virá automática) + slider de ALTURA que recalcula o
  afastamento lateral pela fórmula real com a conta exibida. (c) Desenho em
  ESCALA REAL (px/m uniforme): lote proporcional às dimensões, envelope
  reage a AF/lateral, faixa VERDE pontilhada = TP mínima em m² proporcionais,
  mancha hachurada = projeção máx pela TO (limitada pelo envelope quando ele
  restringe antes — mostrado honestamente). Aviso quando afastamentos
  consomem o lote. (d) Card do mapa do hero agora DESLIZA entre bairros
  (transition left/top .9s + crossfade do texto via classe .trocando) em vez
  de piscar. (e) app.py aceita PORT via env; launch.json da RAIZ (o que o
  preview usa) com autoPort — o servidor manual do Arthur fica na 5000.
- REGRA nova no webapp (07/2026): geocodificação com resultado genérico
  (feature_type fora de address/street) é RECUSADA com mensagem clara em vez
  de gerar ficha de ponto arbitrário — descoberto testando entrada inválida,
  que o Mapbox resolvia para "Belo Horizonte" (centro da cidade).
- PENDENTE (dados): setores internos de ADE (Anexo VII) e camadas OUC/PVP
  (Anexo IV) — hoje viram alerta na ficha, não erro.
- FEITO (07/2026) v2.5, rodada de feedback do Arthur sobre UX:
  (a) hero da landing ganhou toggle Endereço/Índice cadastral (posta direto
  no /consulta com campo `modo`); (b) faixa de stats REMOVIDA a pedido
  ("useless") — contadores saíram do script.js também; (c) CTAs "consultar
  agora" no fim da faixa escura e da calculadora (além do final);
  (d) ficha reorganizada em grupos numerados ("01 · Enquadramento",
  "02 · Parâmetros construtivos"); (e) ESTUDO INTERATIVO repaginado:
  fundo ESCURO (tinta) com a prancha clara dentro (contraste pedido),
  testada/profundidade/área TRAVADAS quando vêm do CTM (Arthur: "é dado,
  não é alterável") — inputs manuais só quando lote não identificado;
  legenda em chips FORA do desenho (antes os rótulos poluíam);
  (f) FÓRMULA CORRIGIDA da projeção máxima: agora limitada por
  min(TO, envelope, área − TP) — a faixa permeável é obrigatória e não
  se constrói sobre ela; a legenda diz QUAL restrição limitou
  ("limitada por TO" vs "por afastamentos + TP"). Antes a mancha invadia
  o verde no desenho — era o bug visual que Arthur apontou.
  (g) EXPORT DA FICHA: botão "Exportar ficha (PDF)" na barra do endereço
  confirmado → modal explicando o valor (opcional, site continua grátis)
  → window.print() com CSS de impressão dedicado (@media print esconde
  nav/busca/modal e clareia o estudo). DECISÃO: será recurso PAGO, mas a
  cobrança real (gateway + verificação) precisa de backend/deploy — vem na
  fase 2; durante a validação o download fica liberado e o modal já avisa
  que será pago. Gateway a decidir: Mercado Pago (Pix nativo, público BR)
  vs Stripe. NÃO fingir paywall sem verificação real.
- FIX (07/2026) v2.5.1 — bug real no CSS do modal: `.modal-fundo` tinha
  `display: flex` sem excluir `[hidden]`, então o atributo `hidden` do HTML
  era ignorado pelo navegador — o modal aparecia direto ao carregar a página
  e os botões de fechar (setar `hidden=true`) não tinham efeito visual.
  Corrigido com `.modal-fundo[hidden] { display: none !important; }`.
  LIÇÃO: sempre que um elemento alterna visibilidade via atributo `hidden`
  E tem uma regra de `display` própria no CSS, checar a precedência — CSS
  de classe SEMPRE vence o atributo `hidden` nativo se não for excluído
  explicitamente. Também: modal agora só abre no clique do botão "Exportar"
  OU sozinho depois de 30s navegando na ficha (uma vez, só se o usuário
  ainda não interagiu de nenhuma forma — clique no X, fora da caixa, Esc ou
  baixar contam como "interagiu"). Conteúdo do modal virou visual (3 ícones
  SVG + selo "grátis sempre") em vez de lista de texto corrida. Legenda do
  TP mínima no anexo interativo (`.leg-cor-verde`) corrigida pra usar o
  MESMO padrão pontilhado do desenho SVG (radial-gradient de pontos, não
  mais cor sólida) — tinha ficado inconsistente visualmente.
- FIX CRÍTICO (07/2026) v2.6 — BUG REAL na testada, achado testando lotes
  reais (Arthur relatou lote comprido aparecendo quase quadrado no anexo
  interativo): `calcular_testadas()` somava QUALQUER aresta do contorno do
  lote perto o bastante de uma via (< 15m), sem checar se a aresta corria
  PARALELA à rua. Em lotes estreitos, uma aresta LATERAL (perpendicular,
  fundo/divisa) perto o bastante da esquina também entrava na soma junto
  com a testada de verdade, inflando o valor pro tamanho do lado comprido
  — em amostra de 500 lotes reais, 43% dos lotes alongados saíam com
  "testada" próxima do lado MAIOR em vez do menor. FIX: nova função
  `_paralela_o_bastante()` compara a direção da aresta com a tangente local
  da via (passo de 2m) e só soma arestas com cos(ângulo) > 0.66 (~até 48°
  de desvio) — descarta arestas perpendiculares mesmo que estejam perto.
  Testado de novo na mesma amostra: erro caiu de 216→27 lotes (a maioria
  dos 27 restantes são esquinas com 2 testadas legítimas, não bug).
- FEITO (07/2026) v2.6 — 4 camadas novas que Arthur baixou do BHMAP:
  `ADE_SETORES_11181.csv` (RESOLVE a maior pendência documentada: setor
  interno de ADE, Anexo VII — antes só um alerta genérico "não identificado
  automaticamente", agora mostra o nome do setor real, ex. "ADE Pampulha -
  Setor Lagoa da Pampulha", como linha própria na ficha "Setor da ADE".
  Resolução item-a-item da regra específica por setor ainda NÃO automatizada
  — fica como próximo passo, mas a informação deixou de estar escondida),
  `BAIRRO_OFICIAL.csv` e `BAIRRO_POPULAR.csv` (point-in-polygon, exibidos no
  bloco de identificação — só aparecem se diferentes um do outro),
  `PROJ_VIARIO_PRIOR_11181.csv` (vira alerta "atingido por Projeto Viário
  Prioritário", espelha o campo do SIURBE). Todas cacheadas em Parquet via
  `scripts/preparar_dados.py`.
- FIX de UX (07/2026) v2.7 — pente-fino no anexo interativo (9 pontos que
  Arthur listou olhando um screenshot real):
  (1) removida a `.moldura` (linha de prancha fixa na viewport) — decorativa
  demais, sem função clara; (2) `.bloco-estudo` agora é FULL-BLEED de
  verdade (100vw via margin negativo calc(-50vw+50%), técnica clássica) —
  precisou de `overflow-x:hidden` em `html` E `body` (só no body não
  bastava: o scroll horizontal do documento é do `html`, não do `body`,
  cuidado se mexer nisso de novo); linhas de texto longo ("Afast. laterais
  e fundos" com a tabela inteira, AMD com todas as vias) substituídas por
  texto curto + botão `.botao-inline` que rola até `#anexo-interativo`, e a
  AMD agora mostra só o valor resolvido pra via REAL do lote
  (`_resolver_amd()` em app.py) — não lista mais LOCAL/COLETORA/ARTERIAL
  quando já sabemos qual é a via; (3) slider de altura vai até 50 m —
  confirmado que o aviso "AFASTAMENTOS CONSOMEM O LOTE" funciona e fica
  legível (fundo terra sólido atrás do texto, testado forçando H alto num
  lote estreito); (4) cotas da planta reformuladas: testada (topo) e
  PROFUNDIDADE NOVA (lado direito, não existia antes) em texto HORIZONTAL
  com halo de contraste (stroke branco, paint-order stroke) em vez de texto
  rotativo -90 minúsculo; ÁREA virou tag estático no canto do lote;
  (5) diferenciação visual estático/dinâmico: AF, T, P e Área em tinta
  neutra (não mudam com o slider); LAT e a mancha de projeção em terra
  (mudam com a altura) — com legenda de cor explicando e badges "muda c/
  altura" nos 2 outputs que realmente dependem de H (Projeção TO e Afast.
  lateral) — potencial CA/quota/TP NÃO mudam com H, só com área/zoneamento;
  (6) parágrafos soltos ("Dimensões do CTM...", "Estudo preliminar...")
  viraram um popover atrás de um botão "i" ao lado do título — o texto
  sempre visível ficou só o essencial; (7) popup de exportar: 30s→60s, e
  agora tem BOTÃO DUPLICADO (topo E rodapé da ficha) — ambos com classe
  `.btn-exportar` (JS usa querySelectorAll, não getElementById); (8) removido
  o alerta genérico "Setores internos de ADE não identificados
  automaticamente" do fim da ficha — ficou FALSO depois que a camada
  ADE_SETORES foi ativada (o aviso específico por ADE já cobre isso, ver
  v2.6); (9) removido "Revisão v0 — EM VALIDAÇÃO" do carimbo (carimbo virou
  grid de 2 colunas em vez de 3).
  LIMITAÇÃO CONHECIDA descoberta testando: pra lotes muito IRREGULARES (área
  bem menor que o retângulo mínimo que os contém — ex. formato em L ou
  triangular), o modelo "testada × (área÷testada)" pode gerar um retângulo
  bem diferente do formato real (testada correta, mas profundidade
  resultante não bate com a profundidade real). É limitação do modelo de
  retângulo equivalente, não bug do cálculo de testada — já avisado na
  interface ("O desenho usa retângulo equivalente").
- INSIGHTS de pesquisa (07/2026, dois PDFs que Arthur trouxe — sizing de
  audiência + dores do fluxo atual): (a) fluxo manual em BH = 4-5 sistemas
  (SIURBE/Ibed + GeoSiurbe + Plantas CP + BHMAP + DECEA) — virou a seção
  "Antes e depois" da landing (aprovada pelo Arthur; hero com números de
  dor ele NÃO aprovou, não fazer); (b) plantão PBH = 400+ agendamentos/mês
  (usado na landing como prova); (c) 2/3 dos arquitetos não usam GIS —
  valida a simplicidade radical; (d) alvo: estudantes primeiro (4-6 mil,
  ~10 faculdades em BH), arquitetos em paralelo (8-10 mil), incorporadoras
  = monetização futura (export/API); (e) RISCO: lei é alvo móvel
  (11.792/2024, mapas atualizados 12/2024 e 01/2026, litígio sobre regra
  de transição do CA art. 356) — manutenção das camadas é o moat; criar
  rotina de verificação de atualização; (f) concorrentes (Urbit,
  Hiperdados) cobrem SP/RJ, não BH — mas podem expandir; velocidade
  importa.
- REFORMA GRANDE (07/2026) v4 — polígono REAL do lote no anexo interativo,
  substituindo o retângulo (testada×profundidade) por engenharia geométrica
  de verdade. Motivada por pergunta do Arthur ("dá pra desenhar o formato
  real com as arestas?"); confirmei viabilidade antes de planejar: 91,6% dos
  lotes têm 6+ vértices (amostra de 2.000 no LOTE_CTM) — a maioria é
  irregular de verdade. Arquitetura:
  - Novo módulo `engine/desenho_lote.py`: `orientar_para_desenho()` (rotaciona
    o lote pra testada ficar embaixo, usando `shapely.affinity`),
    `calcular_envelope()` (recuo NÃO-uniforme por aresta — AF na(s) aresta(s)
    de testada, lateral nas demais — via interseção de retas deslocadas,
    não é um buffer simples), `calcular_faixa_permeavel()` (busca binária pra
    achar o recuo que atinge a área de TP exigida) e `calcular_mancha()`
    (projeção limitada por TO, escalada em direção à testada quando precisa
    encolher — aproximação por escala, não recorte exato, documentada como
    tal no código).
  - `localizar_lote()` agora orienta o polígono CCW (`shapely.geometry.polygon.orient`)
    UMA VEZ, porque `calcular_testadas()` e `preparar_desenho_lote` dependem
    dos MESMOS índices de aresta — reorientar depois quebraria a
    correspondência entre aresta e via.
  - `calcular_testadas()` agora guarda, por grupo de testada, a via
    (classificação, faixa de largura) e os ÍNDICES das arestas — não só o
    nome/comprimento. Isso também resolveu de graça o pedido de lote de
    ESQUINA: cada rua confrontante ganha seu próprio AF resolvido
    (testado num lote real com 2 testadas de 12,5m/12,4m, ambas AF 3,0m —
    mas o mecanismo suporta AFs diferentes por rua).
  - Rota nova `POST /consulta/estudo`: o slider de altura chama o SERVIDOR
    (debounce 130ms) porque o recuo não-uniforme só é robusto com shapely,
    que não roda no navegador — decisão confirmada com o Arthur antes de
    implementar. Reaproveita `_montar_estudo()` pros números que não
    dependem de altura.
  - Teto do slider agora é REATIVO: se uma altura testada volta
    `inconstruivel`, o JS recua o slider pro último valor bom e trava o
    `max` ali — o estado "AFASTAMENTOS CONSOMEM O LOTE" nunca chega a
    aparecer (pedido explícito do Arthur). Testado: lote da Pampulha ficou
    inconstruível entre 30m e 50m, slider trava certinho.
  - Cotas viraram CHAMADA + CAIXA preenchida (linha fina até um retângulo
    com o número dentro, cor tinta=estático/terra=dinâmico) em vez de texto
    solto — pedido de legibilidade. Área do lote virou caixa de destaque
    fixa (canto sup. direito), grande.
  - Botão de reportar (⚑, canto da moldura do desenho): grava em
    `data/relatos_desenho.jsonl` (append simples, sem banco) — lat/lon,
    endereço, tipo (formato/medidas), comentário. Só pra revisão manual
    futura, não bloqueia o usuário.
  BUGS REAIS achados e corrigidos DURANTE a implementação (documentar bem,
  porque são armadilhas de geometria que voltam se alguém mexer aqui sem
  saber):
  1. Offset por aresta pode gerar polígono AUTO-CRUZADO que passa no
     `is_valid` do shapely mas tem área MAIOR que o original em recuos
     grandes (não-monotônico). Fix: todo resultado de offset precisa
     verificar `poly_original.buffer(0.05).contains(resultado)` — um recuo
     pra dentro nunca pode escapar do polígono original.
  2. Busca binária da faixa de TP: quando o offset falha (`None`, recuo
     grande demais pro algoritmo), isso significa "não confio nesse
     resultado", NÃO "consumiu tudo". Tratar como "tudo virou permeável"
     inverte a convergência da busca (bug real: a faixa sempre dava a área
     do lote inteiro).
  3. Direção da busca binária estava invertida: queríamos o MENOR recuo que
     atinge a área mínima de TP (a faixa mais estreita possível), não o
     maior — satisfeito devia apertar `hi`, não `lo`. Confundir isso faz a
     faixa convergir pro lado errado silenciosamente (sem erro, só número
     errado) — só pego testando contra o valor esperado calculado à mão.
  FORA DE ESCOPO: lotes com 3+ ruas continuam "geometria complexa" → modo
  manual (mesmo de antes). Recorte exato da mancha (em vez de escala) fica
  pra depois, se algum caso real mostrar que a aproximação distorce demais.
- FEITO (07/2026) v3.1 — simplificação da landing e acessibilidade p/
  leigos, a pedido do Arthur: removidas as seções "Como funciona" e "Comece
  agora" (redundantes com o resto) e o carimbo-footer (Projeto/Base
  legal/Local/Revisão — informação não essencial); footer virou só o
  aviso + uma linha simples. Nav simplificado (só "A ficha" + "Consultar
  lote"). Seção "A ficha" virou CARROSSEL: 1 item em foco por vez (número,
  título, texto explicativo em linguagem simples pra quem não é da área),
  cicla sozinho a cada 4,2s, com os 8 itens em miniatura embaixo — clicar
  num item assume o foco e reinicia o ciclo dali. Revisei os 8 itens da
  lista (eram nomes técnicos tipo "Quota de terreno"; viraram descrições
  em português simples, e "Alertas"/"Exceções de ADE" concentraram em
  "Dados oficiais do lote" e "Transparência total"). "PBH" trocado por
  "Prefeitura de BH" nos textos voltados ao usuário leigo; "RT" trocado por
  "responsável técnico (arquiteto/engenheiro)". LIÇÃO: o preview do Claude
  Code reporta `prefers-reduced-motion: reduce` como TRUE sempre — qualquer
  auto-ciclo (setInterval) precisa rodar INDEPENDENTE desse flag (só a
  transição/animação visual é que deve respeitar reduced-motion), senão
  parece "quebrado" ao testar aqui. Padrão já usado no mapa vivo do hero,
  replicado agora no carrossel da ficha.
- REBUILD (07/2026) v3 — Arthur reprovou o visual da ficha e do estudo
  ("não está bonito") e pediu redesign do zero mantendo funções:
  (a) LINGUAGEM ÚNICA: toda resposta da ficha agora é CÉLULA de prancha
  (grid 6 colunas, gap 1px cor linha, borda tinta — o idioma que era só do
  CA aplicado a tudo). Seções numeradas com cabeçalho SERIFADO 20px (maior
  que qualquer valor — corrige a hierarquia invertida que Arthur apontou:
  título de seção menor que resposta). Classes novas .fsec/.celulas/.cel;
  classes antigas (linha-param, ident-grade, bloco-estudo, grupo-titulo)
  ficaram órfãs no CSS — limpar um dia.
  (b) ESTUDO INTERATIVO v3: voltou pro papel claro integrado à ficha (o
  bloco escuro full-bleed morreu); layout desenho à esquerda + painel à
  direita com grupos "Do lote — não mudam" e "Dependem da altura" (terra).
  (c) SLIDER COM TETO DINÂMICO: atualizarLimiteAltura() calcula a maior
  altura cujos afastamentos ainda deixam área construtiva
  (latMax = min((T-0,5)/2, P-af-0,5); se <1,5 desabilita slider; se <2,3
  teto 7,5m; senão 12+B·(latMax-2,3), cap 60) — o aviso "afastamentos
  consomem o lote" ficou INATINGÍVEL pelo slider, como Arthur pediu, e
  mostra "máx. p/ este lote: X m". Testado: normal 39,5m; estreito 23,5m;
  degenerado desabilita com mensagem.
  (d) BUG corrigido no rebuild: célula "Projeção máx." (grupo dinâmico)
  exibia a TO bruta (fixa) — agora exibe a projeção EFETIVA (mancha =
  min(TO, envelope, área−TP)), que de fato varia com a altura.
  (e) Fundo milimetrado FIXO (background-attachment: fixed, só ≥900px) —
  o quadriculado fica parado enquanto o conteúdo rola, efeito que Arthur
  pediu. (f) `[hidden]{display:none!important}` global — atributo hidden
  perdia pra display de classe (mesma raiz do bug do modal v2.5.1).
- FIX de UX (07/2026) v2.6 — pente-fino pedido pelo Arthur: (a) TODO campo
  que juntava duas informações com "/" ou "·" virou campo próprio (Setor/
  Quadra/Lote do CTM eram 1 linha, viraram 3; área IPTU vs CTM eram 1 linha,
  viraram 2; Centralidade Local/Conexão Verde eram 1 linha, viraram 2; TP/TO
  eram 1 linha, viraram 2); (b) hierarquia visual unificada — todo título de
  bloco na ficha (grupo-titulo, bloco-identificacao h4, bloco-excecoes h4,
  bloco-alertas h4, estudo-titulo h4) agora usa EXATAMENTE o mesmo estilo
  (mono 10px, letter-spacing .16em, terra ou grafite conforme o tom do
  bloco); todo "valor" de campo (.linha-param .valor, .ident-grade .v)
  padronizado em 14.5px tinta — antes cada bloco tinha um tamanho/cor
  diferente por ter sido escrito em momentos distintos da sessão.
- FEITO (07/2026) v2.4 — Arthur comparou nossa ficha com o relatório oficial
  "Informações Básicas para Edificações" (SIURBE) de um lote real e mandou 6
  CSVs novos do BHMAP p/ `data/geo/`: `LOTE_CTM.csv` (polígono real de cada
  lote, área oficial), `CADASTRO_IMOBILIARIO.csv` (índice cadastral do IPTU,
  endereço oficial, infraestrutura, dados de edificação — 897.874 registros),
  `CENTRALIDADE_LOCAL_11181.csv`, `RECUO_ALINHAMENTO_11181.csv` (ativados),
  `EDIFICACAO.csv` e `LOTE_APROVADO.csv` (NÃO usados ainda — ver "fora de
  escopo" abaixo). Mudanças:
  - `scripts/preparar_dados.py` (rodar manualmente, não no boot): converte os
    CSVs grandes p/ Parquet/GeoParquet em `data/geo/_cache/` — LOTE_CTM cai de
    181MB→68MB e carrega ~8x mais rápido (8s→1s). `NULOTCTM` PRECISA ser lido
    como string (`dtype=str`) — tem zero à esquerda, vira int e quebra o join
    se não especificar.
  - `engine/consulta.py`: `localizar_lote()` (lote CTM mais próximo, None se
    >20m — sem confiança) e `calcular_testadas()` (decompõe o contorno do
    lote em arestas, atribui cada uma à via mais próxima, soma por rua; >2
    ruas confrontantes = `geometria_complexa=true`, cai pro modo manual).
    Validado com endereço real (Fernandes Tourinho 200): área do polígono
    bateu EXATO com AREA_M2 oficial (361.9), testada 33,2m/1 rua. Praça da
    Liberdade corretamente ficou "não identificado" (map como logradouro
    público, >20m do ponto). Centralidade Local e Conexão Verde ativadas
    (point-in-polygon); Recuo de Alinhamento vira alerta com a largura
    prevista do trecho.
  - `engine/indice_cadastral.py`: busca direta por índice cadastral (sem
    geocodificação) — normaliza espaços, junta com LOTE_CTM pelo NULOTCTM,
    usa `representative_point()` (não centroid — pode cair fora em lote
    côncavo). Aba "Índice cadastral" da consulta ATIVA (tirou o "em breve").
  - `_montar_estudo()` (app.py): fator B do afastamento lateral agora é REAL
    quando o lote foi identificado (Centralidade Local do point-in-polygon),
    não mais sempre conservador; testada/área pré-preenchem o anexo
    interativo quando `lote_real` existe e não é complexo (nota "real (CTM)"
    na interface, campos continuam editáveis).
  - Bloco novo "Identificação do lote" na ficha: índice cadastral, endereço
    oficial do IPTU, Setor/Quadra/Lote (derivados do próprio `NULOTCTM` —
    padrão 2+5+5 dígitos, confirmado comparando com o exemplo do SIURBE),
    área IPTU vs área CTM (alerta se divergir >15%), checklist de
    infraestrutura (meio-fio/pavimentação/arborização/galeria pluvial/
    iluminação/esgoto/água/telefonia), dados de edificação existente quando
    há registro (SEMPRE avisa quando o lote tem mais de uma "economia"/unidade
    cadastrada, pra não fingir que os dados são do lote inteiro).
  - FORA DE ESCOPO por enquanto (registrado p/ não esquecer): `EDIFICACAO.csv`
    (altura de edificações via modelo de elevação — visualização futura de
    "já construído"), `LOTE_APROVADO.csv` (planta de parcelamento aprovada,
    sem uso claro ainda), valor venal em R$ (não temos essa tabela, só
    `ZONA_HOMOGENEA` que é código, nunca inventar número), CINDACTA/aeródromo
    (dado da DECEA/Min. Defesa, fora do universo BHMAP), patrimônio cultural
    (provavelmente DPCA-FMC, outro sistema — Arthur confirmou que não tem no
    BHMAP), TDC/BPH/Estoque de Potencial Construtivo/OUC (podem estar em
    LOTE_APROVADO ou exigir camada própria — não confirmado ainda).

- FIX de UX (07/2026) v4.1 — pente-fino pedido pelo Arthur em 5 pontos, depois
  da reforma v4 do polígono real:
  (1) landing: 4º bloco ("Demonstração"/calculadora de potencial) estava
  `.faixa` (fundo claro), quebrando a regra de alternância claro/escuro/claro/
  escuro que os 3 blocos anteriores seguem — virou `.faixa-escura`
  (`templates/landing.html`), com o CTA interno trocado pra `.botao-claro`
  (contraste em fundo escuro, mesmo padrão já usado no bloco "A ficha").
  (2) título do bloco "Antes e depois" trocado por pedido direto: "O caminho
  até os parâmetros de um lote..." (era uma frase fechada, virou reticências).
  (3) BUG REAL achado: `--ok` (verde "disponível" da checklist de
  infraestrutura) NUNCA FOI DEFINIDO em `:root` (`static/style.css`) — só
  existiam `--tinta`, `--terra`, `--papel` etc. Uma custom property CSS
  inexistente usada em `var(--ok)` não dá erro nenhum: cai silenciosamente pro
  valor herdado do ancestral (pra `color`, isso é a cor escura de texto normal,
  não o verde esperado) — por isso NENHUM chip de infraestrutura ficava verde,
  mesmo os presentes. Afetava também `.reportar-obs`, o selo "grátis" do modal
  de exportar e `.ident-real-selo`, não só a checklist. Fix: adicionado
  `--ok: #3E6B4F;` no `:root`. Armadilha a lembrar: variável CSS não definida
  NUNCA quebra nada visivelmente óbvio — só fica "sem efeito", então esse tipo
  de bug só aparece testando visualmente, não em nenhum log/console.
  (4) reordenados os 2 grupos de texto do painel do anexo interativo
  (`templates/consulta.html`): "Do lote — não mudam com a altura" e o
  slider de altura agora vêm ANTES de "Dependem da altura escolhida" (antes a
  ordem tinha o dinâmico primeiro, confuso — o estático deve vir antes do
  controle que causa o dinâmico).
  (5) cotas do desenho: a caixa combinada "testada + AF" (ambos os números
  espremidos numa caixa só, confuso) virou DUAS caixas separadas — uma pra
  testada (aponta pra fora, rumo à rua) e outra pro afastamento frontal
  (aponta pra dentro do lote) — `cotaCaixa()` chamada duas vezes em
  `static/script.js` em vez de uma com texto concatenado. Rótulos abreviados
  "AF"/"LAT" viraram texto completo "Afastamento Frontal"/"Afastamento
  Lateral". Verificado no navegador (lote real, sem sobreposição de caixas):
  `["Testada 27,9 m", "Afastamento Frontal 5,0 m", "Afastamento Lateral 2,55
  m", "ÁREA DO LOTE", "989 m²"]`.
  LIMITAÇÃO OBSERVADA (não é bug desta rodada, achada testando): pra lotes MUITO
  irregulares (ex. Fernandes Tourinho 200 — só 56% de preenchimento do
  retângulo que o contém, contorno com 14 vértices bem côncavo), o algoritmo de
  recuo por aresta pode concluir "inconstruível" em TODA altura testada (3m a
  20m), não só acima de um teto. Isso já aparece corretamente na carga inicial
  da página (H=9 padrão já mostra o aviso, antes de qualquer interação com o
  slider) — não é um travamento silencioso, é o sistema sendo honesto sobre um
  formato que o modelo simplificado não consegue encaixar afastamento nenhum.
  NÃO INVESTIGADO A FUNDO ainda se é uma limitação genuína da geometria real do
  lote (formato realmente aperta demais) ou do algoritmo (aresta jagged
  confundindo o offset por aresta) — decisão de aprofundar ou aceitar como está
  fica pro Arthur.

## Decisões técnicas já tomadas (não reabrir sem motivo)
1. NADA de scraping/agente no site do BHMAP — os dados oficiais são baixáveis
   como shapefile; consulta espacial local é mais barata, estável e precisa.
2. A ficha principal é DETERMINÍSTICA (geo + tabelas), sem LLM. IA entra só na
   fase 3 (chat de dúvidas citando artigos) — reduz custo e alucinação.
3. TP/TO vêm da camada própria (Anexo II), NÃO do zoneamento. Erro clássico a
   evitar.
4. Exceções de ADE prevalecem sobre a regra geral ("Parâmetro prevalente.
   Situações não indicadas seguem a regra geral" — padrão do Anexo XII).
5. Stack alvo fase 2: Supabase (Postgres+PostGIS, auth, controle free/paid) +
   frontend estático no Vercel + geocodificação Google/Mapbox (cota grátis).
6. Caso-limite documentado: via com largura exatamente 15,0 m (lei ">15m",
   shapefile agrupa ">=15m") — tratar de forma conservadora e sinalizar.

## Ética do produto (inegociável)
É informação usada para decisão de projeto real. A ficha SEMPRE exibe:
(a) aviso de que não substitui responsável técnico nem consulta oficial à PBH;
(b) alertas do que o sistema não verificou (setores de ADE, OUC/PVP);
(c) Plano Diretor está em revisão — base legal pode mudar; versionar a lei.
Nunca esconder incerteza para a ficha "parecer completa".

## FEITO (07/2026) — migração pra RAM viável de hospedar + git iniciado
Depois de um conselho de IA (5 perspectivas independentes) analisar o
projeto pra decidir o que fazer antes de ir pro ar, dois pontos de
consenso forte viraram ação imediata:
- **Git iniciado** (`git init` + commit inicial) — projeto não tinha versionamento
  nenhum até aqui (nenhuma versão antiga do código existia de verdade, apesar
  de "v1/v2/v3..." no histórico deste arquivo serem só anotações narrativas).
  `.gitignore` ajustado pra excluir `data/geo/` inteiro (1,5GB de shapefile
  bruto do BHMAP, não é código) e `.env`.
- **BUG ESTRUTURAL DE RAM corrigido**: o motor carregava `LOTE_CTM.parquet`
  (todo lote de Belo Horizonte, 365 mil polígonos) inteiro num GeoDataFrame
  na memória a cada boot — medido em ~562MB de RAM só pra esse arquivo (o
  parquet tem 65MB no disco; vira ~8,6x maior como objeto Shapely em RAM).
  Processo inteiro rodava a ~800-900MB, inviabilizando qualquer hospedagem
  grátis (Render free = 512MB). Trocado por consulta indexada em disco via
  **DuckDB + extensão espacial (índice RTREE)**:
  - Novo módulo `engine/db_lotes.py`: abre conexão read-only a
    `data/geo/_cache/lotes.duckdb` (LOTE_CTM) e `indice_cadastral.duckdb`
    (CADASTRO_IMOBILIARIO/IPTU) — nenhum dos dois carrega o arquivo inteiro
    na memória. `lote_mais_proximo(con, x, y, limiar)` faz
    `WHERE ST_DWithin(geom, ST_Point(x,y), limiar) ORDER BY dist LIMIT 1`,
    usando o índice RTREE — só varre lotes perto do ponto, não os 365 mil.
    `registro_por_indice_cadastral()` e `registros_indice_por_nulotctm()`
    fazem o mesmo pro cadastro do IPTU (chave direta, índice B-tree comum).
  - `scripts/preparar_dados.py` ganhou `construir_db_lotes()` e
    `construir_db_indice()` — rodam depois da conversão CSV→Parquet de
    sempre, geram os `.duckdb` a partir do parquet já existente. Rodar de
    novo sempre que atualizar os CSVs do BHMAP.
  - `engine/consulta.py`: `carregar_camadas()` não chama mais
    `gpd.read_parquet(LOTE_CTM.parquet)` nem `pd.read_parquet(INDICE_CADASTRAL)`
    — abre as 2 conexões DuckDB. `localizar_lote()` reescrita pra consultar
    `lote_mais_proximo()` em vez de `.distance()` no GeoDataFrame inteiro;
    mesmo formato de retorno de antes (`{"row", "poly", "distancia_m"}`),
    só que `row` agora é um dict simples (só usa `.get()`, compatível).
  - `engine/indice_cadastral.py` (`buscar_por_indice`) e
    `webapp/app.py` (`_montar_identificacao`) também migrados pras novas
    funções — nenhuma mudança de comportamento visível, só a fonte do dado.
  - **Resultado medido** (mesmo processo, mesma máquina): RAM caiu de
    ~800-900MB pra **~270-277MB**. Consulta real testada (endereço, índice
    cadastral, lote inconstruível, slider de altura) sem regressão.
  - `requirements.txt` criado (não existia) com `duckdb` incluído.
  ARMADILHA se mexer nisso de novo: RTREE do DuckDB exige a coluna de
  geometria como `GEOMETRY` puro (sem CRS no tipo) — `geometry::GEOMETRY`
  no CREATE TABLE, senão dá `Binder Error: RTree indexes can only be
  created over GEOMETRY columns` mesmo a coluna já sendo geometria.

## Roteiro
- Fase 1.5 (ATUAL): geocodificação endereço→lat/lon + bateria de testes com os
  endereços de resposta conhecida do Arthur. GATE: só ir p/ fase 2 se bater.
- Fase 2: site (landing + ficha + login + freemium). Guiar Arthur do zero.
- Fase 3: chat "dúvida específica" com IA citando artigo da lei (docs/
  lei_completa.txt tem os 410 artigos em texto).

## Estrutura
```
data/geo/       shapefiles + CSVs do BHMAP (EPSG:31983) — viária e os CSVs
                novos (LOTE_CTM, CADASTRO_IMOBILIARIO etc.) são grandes, fora do zip
data/geo/_cache/  Parquet/GeoParquet + lotes.duckdb/indice_cadastral.duckdb
                gerados por scripts/preparar_dados.py — não versionar
data/params/    Anexo XII em JSON (ca_quota.json, afastamentos_alturas.json)
engine/consulta.py       motor: python3 engine/consulta.py <lat> <lon> [--json]
engine/db_lotes.py       consulta indexada (DuckDB) do LOTE_CTM e do IPTU — não carrega na RAM
engine/geocode.py        endereço -> lat/lon (Mapbox)
engine/indice_cadastral.py   índice cadastral -> lat/lon (direto, sem geocodificação)
scripts/preparar_dados.py    converte CSVs grandes p/ Parquet + constrói os .duckdb — rodar após CSV novo/atualizado
webapp/         Flask local (landing + consulta) — sem login/banco/deploy ainda
docs/           lei_completa.txt, anexo12.txt, ficha_conferencia.html
```

## Comandos úteis
```
pip install geopandas requests python-dotenv pyarrow   # dependências (Windows: sem --break-system-packages)
python scripts/preparar_dados.py                  # converte CSVs novos p/ Parquet (rodar 1x após CSV novo)
python engine/consulta.py -19.9319 -43.9377       # teste por coordenada: Praça da Liberdade
python engine/consulta.py --endereco "Praça da Liberdade"   # teste por endereço (geocodifica via Mapbox)
python webapp/app.py                              # sobe o site local (localhost:5000)
```
Token Mapbox em `.env` na raiz (`MAPBOX_TOKEN=...`), nunca versionado.
