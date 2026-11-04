# Gabarito — visão e plano
### Escrito em 11/10/2026, depois da análise do Sitescope e do despejo de ideias do Arthur

Este documento guarda a VISÃO (o que o Gabarito quer ser) e o PLANO (em que
ordem chegar lá). É o documento de direção: o CLAUDE.md guarda o que já foi
feito e as armadilhas técnicas; aqui fica para onde vamos.

Regra deste arquivo: **separar o que foi verificado do que é aposta.** Toda
afirmação técnica abaixo está marcada como `[VERIFICADO]`, `[PROVÁVEL]` ou
`[NÃO VERIFICADO]`.

---

## 1. Onde estamos (11/10/2026)

No ar e funcionando: consulta por endereço e índice cadastral, ficha completa
(zoneamento, ADEs, CA, TP/TO, afastamentos, CINDACTA ao vivo, proteção
cultural, APP), estudo interativo com envelope construtivo em polígono real,
construção existente (voo 2015 + projetos aprovados), exportação DXF, link
compartilhável, 404 e favicon próprios.

Tração: 326 usuários em 16 dias (ago/2026, divulgação por WhatsApp), e um
e-mail não solicitado do **diretor de pesquisa e análise aplicada da SUPLAN/PBH** oferecendo estágio por causa do site — a área dele é
"automação de diagnóstico e prognóstico de cenários de intervenções e
legislações urbanas", ou seja, o mesmo problema pelo lado de dentro do órgão.

---

## 2. O benchmark: Sitescope (sitescope.ai)

Analisado em 11/10/2026. Tudo abaixo é `[VERIFICADO]` — veio do artefato
público (PDF de exemplo de 97 páginas, Knowledge Hub, termos de serviço).

**Quem são:** Sitescope sp. z o.o., Varsóvia. KRS 0001187643, capital social
PLN 6.000 (o mínimo legal), 5 funcionários, 75 seguidores no LinkedIn,
fundador Albert Bigoszewski, sede em apartamento. Dos 3 produtos anunciados,
**só 1 existe**: a API diz "we are developing", o Studio só tem "book a demo".

**O que o produto deles é:** relatório de lote com 36 seções em 7 categorias,
modular (paga só pelas seções escolhidas), por parcela, sem necessidade de
conta, com PDF white-label (logo do cliente). PDF de exemplo: 97 páginas,
43 mapas.

**O achado mais importante:** na lista de seções deles, "Development capacity
— *Coming soon*". **O envelope construtivo é a única coisa que eles ainda não
entregaram, e é exatamente o que o Gabarito já faz.** Eles são amplos em
leitura de dado; nós somos fundos em simulação. A simulação é a parte difícil.

**O padrão de cada seção deles** (vale copiar):
mapa com legenda própria → tabela de números → **"como interpretar este
resultado"** → fontes item a item → **carimbo com hora exata da leitura**.
Nós já temos fontes por seção; falta o "como ler" e o carimbo de hora.

**Onde eles ganham de nós:** visual e sensação de profissionalismo; amplitude
(36 seções × nossas ~8); multi-lote (remembramento); presença online.

**Onde nós ganhamos deles:** envelope construtivo, slider de altura com
recálculo geométrico real, DXF para CAD, gratuito e sem fricção de checkout.

---

## 3. A visão (palavras do Arthur, 11/10/2026)

> "We can be BH map, but better."

Não é um site de consulta de parâmetro. É uma **plataforma de visualização e
consulta de dados urbanos de BH**, onde:

1. O lote aparece num **mapa**, centralizado, com o entorno — causa impressão
   imediata em quem chega pela primeira vez.
2. Existe uma **visão 3D isométrica**: o lote e as construções vizinhas na
   altura real, alternável com o 2D num clique, girável, com camadas que
   ligam e desligam.
3. **Toda camada que temos vira informação E vira camada no mapa** — transporte
   público, metrô, curso d'água, praça, unidade de conservação, linha de
   transmissão. "Se eu tenho o dado, tem que estar lá."
4. **Tudo é baixável**: o usuário escolhe quais camadas quer e baixa um CAD só
   com aquelas. Lote sozinho, lote + entorno, + curvas de nível, + o que ele
   marcar.
5. A partir da visualização vêm os **estudos**: sombra projetada dos vizinhos,
   insolação, declividade.
6. **Busca reversa**: hoje a pergunta é "me fale deste lote". A visão é também
   "me mostre todos os lotes da cidade que são assim" — por bairro, por
   padrão, por camada. Encontrar padrões no dado, não só consultar um ponto.

Posicionamento que isso cria: deixa de ser "estudante facilitando a vida de
arquiteto" e passa a ser ferramenta técnica séria. Palavras dele: *"that makes
us a fucking technological savant to anyone looking at it from outside."*

---

## 4. Descobertas técnicas que sustentam a visão

### 4.1 Curvas de nível paradas no disco `[VERIFICADO]`
`data/geo/CURVA_DE_NIVEL_5M/CURVA_DE_NIVEL_5M.shp` — 139,8 MB, baixado em
julho/2026, nunca usado. Dados limpos: 3.699 linhas, campo `COTA`, cota de
675 a 1.505 m, EPSG:31983 (mesmo CRS de tudo).

Convertido para DuckDB com índice RTREE: consulta em **56 ms por lote**.
Medição em 400 lotes reais (desnível no entorno de 80 m):

| desnível | lotes |
|---|---|
| até 5 m | 8% |
| 5–15 m | 28% |
| 15–30 m | 44% |
| > 30 m | 19% |

Mediana 20 m. **BH é uma cidade de morro** — compare com o lote de exemplo do
Sitescope, na Polônia: 3,72 m de desnível em 9.972 m². Declividade é seção 21
de 36 para eles e é manchete para nós.

RESSALVA `[VERIFICADO]`: curvas de 5 em 5 m são grossas para um lote pequeno.
Serve para dizer "este terreno está numa encosta de 20 m" e **não** para
cravar "a declividade deste lote é 12,4%". Precisão real exigiria modelo
digital de terreno em grade, que ainda não procuramos `[NÃO VERIFICADO]`.

ARMADILHA `[VERIFICADO]`: laço com `gpd.read_file(bbox=)` + `shapely.distance`
**trava o processo** neste ambiente (`PyEval_SaveThread: GIL not held`),
reproduzido 4 vezes. O caminho de produção é DuckDB espacial, sem shapely no
laço — que funcionou de primeira.

### 4.2 Já temos altura de 728 mil construções e usamos só no próprio lote `[VERIFICADO]`
`EDIFICACAO.parquet` (34 MB, no ar desde 04/10) tem contorno + altura de toda
construção de BH. Hoje mostramos só as do lote consultado. Ampliar para raio
de 100 m é quase de graça e destrava:
- seção "entorno construído" (o que o Sitescope tem na seção 5);
- **extrusão 3D das construções vizinhas** — é o dado que torna a visão 3D
  possível sem modelar nada à mão;
- **estudo de sombra** dos vizinhos sobre o terreno (ninguém em BH faz).

### 4.3 Camadas da PBH que nunca tocamos `[VERIFICADO]`
Inventário do `geosiurbe` em 11/10/2026: 47 camadas, usamos 17. Não usadas e
relevantes:

`ESTACAO_ONIBUS` · `LINHA_METRO` · `CURSO_DAGUA_MB` · `UNID_CONSERV_AMBIENTAL`
`PRACA` · `LINHA_TRANSMISSAO` · `SUBESTACAO_ENERGIA_MB` · `QUADRA_CTM`
`FERROVIA` · `LIMITE_MUNICIPIO` · `REGIONAL` · `BHMAP_CA_BASICO`
`BHMAP_PLANTA_CP` · `BHMAP_LOTES_PEBII` · `BHMAP_AEIS_INTERESSE_AMBIENTAL`
`BHMAP_BEM_CULTURAL_IMATERIAL` · `BHMAP_OPERACAO_URBANA_NOVALEI`

O portal novo (`geoservicos.pbh.gov.br`, 342 camadas) devolveu 403 nesta
tentativa — tem firewall, precisa dos cabeçalhos certos `[NÃO VERIFICADO]`.

### 4.4 O 3D provavelmente não é um projeto de pesquisa `[PROVÁVEL]`
MapLibre GL JS (fork livre do Mapbox GL) faz `fill-extrusion` nativo: extruda
polígono por um atributo de altura. Nós temos polígono + altura de 728 mil
construções. Isso significa que a visão 3D é, em boa parte, **configuração de
camada**, não motor gráfico novo.

Pendências a verificar antes de prometer `[NÃO VERIFICADO]`:
- como servir as camadas (hipótese: PMTiles pré-gerado — arquivo estático,
  sem servidor, bom para o Render free);
- custo de RAM/banda no plano gratuito;
- se vale MapLibre (grátis) ou Mapbox GL (já pagamos o geocoding).

---

## 5. O plano, em ordem

A ordem não é por tamanho nem por empolgação: é por **dependência**. O mapa é
a fundação de quase tudo que o Arthur quer. Hoje o Gabarito **não tem mapa
nenhum** (decisão consciente do MVP em julho: "sem mapa interativo"). Essa
decisão agora está vencida.

```
FASE 0  arrumar o que existe        (independente, rápido)
   │
FASE 1  MAPA  ◄── a fundação
   ├── FASE 2  camadas ligáveis/desligáveis
   │      └── FASE 3  download por camada escolhida
   ├── FASE 4  terreno (declividade) ──┐
   └── FASE 5  3D  ◄── precisa de 1, e o terreno da 4 vira a malha
          └── FASE 6  sombra e insolação
                 └── FASE 7  busca reversa / escala de bairro
```

### Andamento
- **04/11/2026 — Fases 0 e 1 implementadas (local).** Título some com ficha na tela;
  estudo com slider na coluna da esquerda e grupos recolhíveis ("Mudam com a altura",
  "Do lote", "O que já existe" fechado). Mapa no topo: MapLibre + fundo OpenFreeMap
  (OpenStreetMap, sem chave, sem custo), contorno do CTM do lote e vizinhos num raio de 90 m
  pela rota `/consulta/mapa` (DuckDB em disco; RAM medida: 329 MB antes e depois de 30
  mapas). Decisão: a Fase 1 NÃO precisou de PMTiles; ele só entra na Fase 2 (camadas da
  cidade inteira).

### FASE 0 — Arrumar o que já existe
*Independente de tudo. Pode ser feito já.*

1. **Espaço desperdiçado na /consulta.** Tirar (ou enfiar sob a barra do topo)
   o título "Consultar lote" e o subtítulo "Ficha urbanística pela Lei
   11.181/19". Subir a barra de endereço. O espaço liberado é onde o mapa vai.
2. **Painel do estudo interativo com scroll demais.** A coluna da direita
   ficou grande demais e parece inacabada. Transformar os grupos em blocos
   **recolhíveis**, com três categorias:
   - "Do lote — não mudam com a altura"
   - "O que já existe no lote"
   - **nova:** "Mudam com a altura pretendida" (afastamento lateral + área
     construtiva máxima)
3. **Slider de altura muda de lugar:** vai para a coluna da ESQUERDA, logo
   abaixo do desenho. Os números que ele gera (afastamento lateral, área
   construtiva) continuam na coluna da DIREITA.

### FASE 1 — O mapa
*A fundação. É também o maior ganho de primeira impressão.*

Mapa na /consulta, no espaço liberado pela Fase 0, entre a barra de endereço e
o começo da ficha. Características pedidas:
- lote **centralizado** e **colorido com destaque**;
- ruas e lotes vizinhos visíveis;
- **sem borda definida — o mapa desvanece (fade) e sangra por trás dos blocos
  de informação**;
- não é um mapão: ocupa aproximadamente o espaço que o título ocupava.

### FASE 2 — Camadas ligáveis
Toda camada que temos vira botão de ligar/desligar sobre o mapa. Começa pelas
que já estão no banco (zoneamento, ADE, APP, proteção cultural, viário) e
incorpora as 17 não usadas da seção 4.3. Princípio do Arthur: **se temos o
dado, ele aparece — como informação na ficha, como camada no mapa, ou os dois.**

### FASE 3 — Download por camada
O botão de CAD ganha um irmão no TOPO, perto do mapa (o de baixo continua).
Ao clicar, o usuário **escolhe o que quer no arquivo**: só o lote; lote +
entorno; + curvas de nível; + qualquer camada ligada. Gera o DXF só com
aquilo. Isso reaproveita o `engine/dxf_lote.py` que já existe e o sistema de
camadas da Fase 2.

### FASE 4 — Terreno
Curvas de nível (4.1) viram: faixa de declividade do lote, desnível, perfil do
terreno, e **camada no mapa**. Também é a malha de terreno que o 3D vai usar.

### FASE 5 — 3D
Visão isométrica: lote + construções vizinhas extrudadas na altura real
(dado 4.2), sobre o terreno (dado 4.4). Alternância 2D/3D num clique, giro,
camadas ligáveis herdadas da Fase 2.

### FASE 6 — Sombra e insolação
Depende do 3D. Sombra projetada dos vizinhos sobre o lote ao longo do dia e do
ano. É análise de arquiteto, não de corretor — e o Sitescope não tem.

### FASE 7 — Escala de bairro e busca reversa
Inverter a pergunta: em vez de "me fale deste lote", "me mostre todos os lotes
que são assim". Por bairro, por padrão, por camada. Encontrar padrões.
Possivelmente uma aba nova ou um site irmão.

---

## 6. Crescer a base de usuários

Duas opções que o Arthur levantou:
- **A: região metropolitana de BH** (Contagem, Betim, Nova Lima, Sabará...)
- **B: outras capitais do Brasil** — ele acha que tem mais potencial

**Contraponto honesto, para decidir depois.** A opção B tem mais potencial
*e* custa desproporcionalmente mais, porque o valor do Gabarito não está no
mapa: está na **integração entre lei e dado**, que é por cidade. Cada capital
tem outro plano diretor, outro cadastro, outro portal, outras siglas. O motor
hoje é cheio de premissa de BH: Lei 11.181/19, CTM, índice cadastral do IPTU,
CINDACTA, Anexo XII.

Existe uma terceira opção que não foi levantada: **aprofundar BH até o produto
ficar inegável, generalizando o motor no caminho** — aí a segunda cidade custa
uma fração, porque o motor já separa "regra da cidade" de "mecânica do
cálculo". Hoje ela custaria quase um projeto novo.

Decisão: em aberto. Não decidir agora; decidir depois das Fases 1–3, quando o
produto estiver mais forte e a generalização do motor estiver mais clara.

---

## 7. Decisões registradas

- **PDF pago / white-label: ENGAVETADO.** O Arthur conhece a ideia (o PDF
  chegou a existir e foi retirado porque matava o retorno ao site). Não vamos
  implementar por enquanto. Fica na prateleira.
- **DXF continua gratuito** — é matéria-prima por lote, traz a pessoa de volta.
- **Usar todas as camadas disponíveis** — decisão explícita, sem exceção.
- **O mapa deixa de ser "fora do MVP"** — a decisão de julho/2026 de não ter
  mapa está formalmente revogada.

---

## 8. O que é o "Knowledge Hub" (o Arthur perguntou)

É uma **página separada do produto, que explica o produto**. No Sitescope, cada
uma das 36 seções tem uma entrada com quatro blocos fixos:

1. *O que esta seção mostra* — a lista de campos que aparecem
2. *Por que isso importa* — para que serve na prática
3. *Como ler o resultado* — como interpretar, e as pegadinhas
4. *Fontes* — de onde vem

Serve a três coisas ao mesmo tempo: ensina o usuário, é o catálogo de vendas
("veja o que você leva"), e é **conteúdo que o Google indexa**.

Esse terceiro ponto resolve um problema real e medido nosso: em 04/10 o Google
mostrava um pedaço do rodapé como descrição do site, porque o Gabarito quase
não tem conteúdo indexável — a home, o formulário, e as fichas bloqueadas no
robots por causa do CINDACTA ao vivo. Uma página dessas é conteúdo indexável
que **não** expõe ficha nenhuma.

---

## 9. Pendências herdadas (não esquecer)

- Zip de dados: o `dados_producao.zip` (148,5 MB) está na release `dados-v1`
  do GitHub; trocar o asset com o MESMO nome mantém a URL que o Render baixa.
- Deploy do Render já ficou preso uma vez (04/10): o push não gerou publicação
  e um commit vazio destravou. Se demorar mais de ~5 min, suspeitar.
- Google ainda deve estar mostrando o favicon antigo (cache de dias a semanas);
  acelerar pedindo indexação da home no Search Console.
