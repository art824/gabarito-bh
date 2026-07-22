/* Gabarito — interações (vanilla JS, sem dependências) */
(function () {
  "use strict";

  var reduzMovimento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Sonda: o IntersectionObserver dispara neste ambiente?
     (Alguns renderers sem frames nunca chamam o callback.) */
  var ioSaudavel = false;
  try {
    var sonda = new IntersectionObserver(function () {
      ioSaudavel = true;
      sonda.disconnect();
    });
    sonda.observe(document.body);
  } catch (e) { /* sem suporte — fallback cuida */ }

  function fmtBR(n, casas) {
    return n.toLocaleString("pt-BR", { minimumFractionDigits: casas || 0, maximumFractionDigits: casas || 0 });
  }

  /* Google Analytics: eventos personalizados (no-op se o gtag não carregou,
     ex. bloqueador de anúncios — nunca pode quebrar o site) */
  function ga(evento, params) {
    if (typeof window.gtag === "function") window.gtag("event", evento, params || {});
  }

  /* ficha carregada = uma consulta bem-sucedida foi exibida */
  if (document.getElementById("est-altura")) ga("consulta_visualizada");

  /* primeiro uso do slider de altura nesta página */
  var _sliderGA = document.getElementById("est-altura");
  if (_sliderGA) {
    var _sliderUsado = false;
    _sliderGA.addEventListener("input", function () {
      if (!_sliderUsado) { _sliderUsado = true; ga("slider_altura_usado"); }
    });
  }

  /* ---------- 1. Mapa vivo de BH: pings em loop com dados reais ---------- */
  var mapa = document.getElementById("mapa-vivo");
  if (mapa) {
    var dadosMapa = JSON.parse(document.getElementById("dados-mapa").textContent);
    var ping = document.getElementById("ping");
    var miniFicha = document.getElementById("mini-ficha");
    var mfBairro = miniFicha.querySelector(".mf-bairro");
    var mfDados = miniFicha.querySelector(".mf-dados");
    var VB_W = 420, VB_H = 520;

    /* embaralha uma vez p/ variar a ordem geográfica */
    for (var s = dadosMapa.length - 1; s > 0; s--) {
      var j = Math.floor(Math.random() * (s + 1));
      var tmp = dadosMapa[s]; dadosMapa[s] = dadosMapa[j]; dadosMapa[j] = tmp;
    }

    var idxPing = -1, primeiraFicha = true;

    function aplicarPonto(p) {
      ping.setAttribute("transform", "translate(" + p.x + " " + p.y + ")");
      ping.setAttribute("opacity", "1");
      ping.classList.remove("ativo");
      void ping.getBoundingClientRect(); /* força reinício das ondas */
      ping.classList.add("ativo");

      mfBairro.textContent = p.nome;
      mfDados.textContent = p.sigla + " · CA MÁX " + p.ca;
      miniFicha.style.left = (p.x / VB_W * 100) + "%";
      miniFicha.style.top = (p.y / VB_H * 100) + "%";
      miniFicha.classList.toggle("abaixo", p.y < 110);
    }

    function proximaConsulta() {
      idxPing = (idxPing + 1) % dadosMapa.length;
      var p = dadosMapa[idxPing];

      if (primeiraFicha || reduzMovimento) {
        primeiraFicha = false;
        aplicarPonto(p);
        miniFicha.hidden = false;
        void miniFicha.offsetWidth;
        miniFicha.classList.add("visivel");
        return;
      }
      /* transição suave: texto some, card desliza até o novo ponto, texto surge */
      miniFicha.classList.add("trocando");
      setTimeout(function () {
        aplicarPonto(p);
        setTimeout(function () { miniFicha.classList.remove("trocando"); }, 450);
      }, 220);
    }
    proximaConsulta();
    setInterval(proximaConsulta, 3400);
  }

  /* ---------- 2. Reveals no scroll ---------- */
  var reveals = document.querySelectorAll(".reveal");
  if (reveals.length) {
    var obsReveal = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          e.target.classList.add("visivel");
          obsReveal.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });
    reveals.forEach(function (el) { obsReveal.observe(el); });
  }

  /* ---------- 3. Alternância endereço/índice no hero da landing ---------- */
  var heroModos = document.getElementById("hero-modos");
  if (heroModos) {
    var heroModo = document.getElementById("hero-modo");
    var heroEndereco = document.getElementById("busca-input");
    var heroIndice = document.getElementById("busca-indice");
    heroModos.querySelectorAll(".hm").forEach(function (btn) {
      btn.addEventListener("click", function () {
        heroModos.querySelectorAll(".hm").forEach(function (b) { b.classList.remove("ativo"); });
        btn.classList.add("ativo");
        heroModo.value = btn.dataset.modo;
        var indice = btn.dataset.modo === "indice";
        heroEndereco.hidden = indice;
        heroIndice.hidden = !indice;
        (indice ? heroIndice : heroEndereco).focus();
      });
    });
  }

  /* ---------- 3b. Overlay de carregamento no envio do form da home ----------
     Igual ao esqueleto da página de consulta, mas em tela cheia: aqui a
     busca navega pra OUTRA página (/consulta), então não dá pra mostrar um
     esqueleto da ficha — só um "consultando..." cobrindo a tela até a nova
     página chegar (a consulta pode levar alguns segundos: geocodificação +
     motor + a consulta ao vivo do CINDACTA). */
  var buscaHero = document.querySelector(".busca-hero");
  var overlayCarregando = document.getElementById("carregando-overlay");
  if (buscaHero && overlayCarregando) {
    buscaHero.addEventListener("submit", function () {
      var modo = document.getElementById("hero-modo").value;
      var campo = modo === "indice" ? document.getElementById("busca-indice") : document.getElementById("busca-input");
      if (!campo || !campo.value.trim()) return;
      overlayCarregando.hidden = false;
      overlayCarregando.setAttribute("aria-hidden", "false");
      var btn = buscaHero.querySelector('button[type="submit"]');
      if (btn) { btn.disabled = true; btn.textContent = "Consultando…"; }
    });
  }

  /* ---------- 4. Calculadora de potencial construtivo (landing) ---------- */
  var slider = document.getElementById("calc-area");
  if (slider) {
    var areaOut = document.getElementById("calc-area-out");
    var outBas = document.getElementById("out-bas");
    var outMax = document.getElementById("out-max");
    var zonaNome = document.getElementById("calc-zona-nome");
    var volBas = document.getElementById("vol-bas");
    var volMax = document.getElementById("vol-max");
    var cotaBas = document.getElementById("cota-bas");
    var cotaMax = document.getElementById("cota-max");
    var zonas = Array.prototype.slice.call(document.querySelectorAll(".zona"));

    var CA_TETO = 5.0;      /* maior CA do seletor — referência da escala */
    var ALTURA_MAX = 240;   /* px de altura do maior volume no SVG */
    var CHAO = 270;         /* y da linha do terreno no SVG */

    function zonaAtiva() {
      var z = document.querySelector(".zona.ativo");
      return {
        nome: z.firstChild.textContent.trim(),
        bas: parseFloat(z.dataset.bas),
        max: parseFloat(z.dataset.max)
      };
    }

    function atualizar() {
      var area = parseInt(slider.value, 10);
      var z = zonaAtiva();
      var potBas = area * z.bas;
      var potMax = area * z.max;

      areaOut.textContent = fmtBR(area) + " m²";
      outBas.textContent = fmtBR(potBas);
      outMax.textContent = fmtBR(potMax);
      zonaNome.textContent = z.nome;

      var hBas = Math.max(14, (z.bas / CA_TETO) * ALTURA_MAX);
      var hMax = Math.max(14, (z.max / CA_TETO) * ALTURA_MAX);
      volBas.setAttribute("y", CHAO - hBas);
      volBas.setAttribute("height", hBas);
      volMax.setAttribute("y", CHAO - hMax);
      volMax.setAttribute("height", hMax);
      cotaBas.setAttribute("y", CHAO - hBas - 10);
      cotaBas.textContent = fmtBR(potBas) + " m²";
      cotaMax.setAttribute("y", CHAO - hMax - 10);
      cotaMax.textContent = fmtBR(potMax) + " m²";
    }

    slider.addEventListener("input", atualizar);
    zonas.forEach(function (btn) {
      btn.addEventListener("click", function () {
        zonas.forEach(function (b) { b.classList.remove("ativo"); });
        btn.classList.add("ativo");
        atualizar();
      });
    });
    atualizar();
  }

  /* ---------- 4b. Fallback de segurança ----------
     Se o IntersectionObserver estiver quebrado neste ambiente (a sonda
     nunca disparou), nada pode ficar escondido: após 2,5s ativa tudo. */
  setTimeout(function () {
    if (ioSaudavel) return;
    reveals.forEach(function (el) { el.classList.add("visivel"); });
  }, 2500);

  /* ---------- 4e. PDF: abrir todos os <details> ao imprimir ----------
     Um <details> fechado não revela o conteúdo só escondendo o summary no
     CSS — o navegador o mantém colapsado. Então abrimos todos antes de
     imprimir (fontes, "ver o que foi verificado") e restauramos depois. */
  (function () {
    var estadoDetails = [];
    window.addEventListener("beforeprint", function () {
      estadoDetails = [];
      document.querySelectorAll("details").forEach(function (d) {
        estadoDetails.push([d, d.open]);
        d.open = true;
      });
    });
    window.addEventListener("afterprint", function () {
      estadoDetails.forEach(function (par) { par[0].open = par[1]; });
    });
  })();

  /* Potencial construtivo: agora é 100% renderizado no servidor (gráfico +
     números), sem interatividade — a área é dado do lote, não algo a variar. */

  /* ---------- 6. Anexo interativo — polígono real do lote ----------
     Quando o lote foi identificado no CTM, o contorno/envelope vêm do
     SERVIDOR (precisa de shapely pra recuo geométrico não-uniforme —
     AF na testada, lateral nas demais arestas — isso não dá pra fazer
     com confiança em JS puro). O slider chama /consulta/estudo com
     debounce. Sem lote identificado, cai no modo manual (retângulo
     simples, calculado no cliente, sem rede). */
  var dadosEstudoEl = document.getElementById("dados-estudo");
  if (dadosEstudoEl) {
    var est = JSON.parse(dadosEstudoEl.textContent);
    var $ = function (id) { return document.getElementById(id); };
    var svgNS = "http://www.w3.org/2000/svg";
    var inT = $("est-testada"), inP = $("est-prof"), inH = $("est-altura");
    var temPoligono = !!est.desenho_inicial;

    function afastLateral(h, fatorB) {
      if (h < 8) return 1.5;
      if (h <= 12) return 2.3;
      return 2.3 + (h - 12) / fatorB;
    }
    var afEfetivo = (est.af_exc !== null && est.af_exc !== undefined) ? est.af_exc
                  : (est.af !== null && est.af !== undefined) ? est.af : null;

    function legenda(id, txt) {
      var el = $(id);
      if (el) { el.textContent = txt; el.parentElement.hidden = !txt; }
    }
    function svgEl(tag, attrs) {
      var el = document.createElementNS(svgNS, tag);
      for (var k in attrs) el.setAttribute(k, attrs[k]);
      return el;
    }
    function limparGrupo(id) {
      var g = $(id);
      while (g.firstChild) g.removeChild(g.firstChild);
      return g;
    }
    function bbox(pontos) {
      var minx = Infinity, maxx = -Infinity, miny = Infinity, maxy = -Infinity;
      pontos.forEach(function (p) {
        if (p[0] < minx) minx = p[0]; if (p[0] > maxx) maxx = p[0];
        if (p[1] < miny) miny = p[1]; if (p[1] > maxy) maxy = p[1];
      });
      return { minx: minx, maxx: maxx, miny: miny, maxy: maxy };
    }
    function normalSaida(p0, p1) {
      /* normal à DIREITA da aresta = lado exterior, pra polígono CCW */
      var dx = p1[0] - p0[0], dy = p1[1] - p0[1];
      var comp = Math.hypot(dx, dy) || 1;
      return [dy / comp, -dx / comp];
    }

    var RUA_Y = 300, CX = 190, MAXW = 226, MAXH = 250;

    function criarTransform(contorno) {
      var bb = bbox(contorno);
      var largura = Math.max(bb.maxx - bb.minx, 1);
      var altura = Math.max(bb.maxy - bb.miny, 1);
      var esc = Math.min(MAXW / largura, MAXH / altura);
      var cxm = (bb.minx + bb.maxx) / 2;
      return { esc: esc, pt: function (x, y) { return [CX + (x - cxm) * esc, RUA_Y - y * esc]; } };
    }
    function pathD(pontos, tr) {
      return pontos.map(function (p, i) {
        var xy = tr.pt(p[0], p[1]);
        return (i === 0 ? "M" : "L") + xy[0].toFixed(1) + "," + xy[1].toFixed(1);
      }).join(" ") + " Z";
    }

    function pontoNaDirecao(ancora, direcao, dist) {
      var comp = Math.hypot(direcao[0], direcao[1]) || 1;
      return [ancora[0] + (direcao[0] / comp) * dist, ancora[1] + (direcao[1] / comp) * dist];
    }
    var ROTULOS_VIA = { "LOCAL": "Via Local", "COLETORA": "Via Coletora", "ARTERIAL": "Via Arterial", "LIGACAO REGIONAL": "Ligação Regional" };
    function _rotuloClasseVia(classificacao) {
      return ROTULOS_VIA[classificacao] || classificacao;
    }
    function pontoMedioArestas(contorno, indices, n) {
      var somaX = 0, somaY = 0, cont = 0;
      indices.forEach(function (i) {
        var p0 = contorno[i], p1 = contorno[(i + 1) % n];
        somaX += (p0[0] + p1[0]) / 2; somaY += (p0[1] + p1[1]) / 2; cont++;
      });
      return cont ? [somaX / cont, somaY / cont] : contorno[0];
    }
    function renderizar(d, H) {
      var gLote = limparGrupo("g-lote"), gMancha = limparGrupo("g-mancha"),
          gCotas = limparGrupo("g-cotas"), gAviso = limparGrupo("g-aviso");
      var n = d.contorno.length - 1;
      var tr = criarTransform(d.contorno);

      gLote.appendChild(svgEl("path", { d: pathD(d.contorno, tr), fill: "#FBF8F0", stroke: "#14202C", "stroke-width": "2" }));

      if (d.inconstruivel) {
        legenda("leg-mancha", "");
        var bb = bbox(d.contorno);
        var centro = tr.pt((bb.minx + bb.maxx) / 2, (bb.miny + bb.maxy) / 2);
        gAviso.appendChild(svgEl("rect", { x: centro[0] - 74, y: centro[1] - 22, width: 148, height: 44, fill: "#B0402C", opacity: "0.94" }));
        var texto = svgEl("text", {
          x: centro[0], y: centro[1] - 6, "text-anchor": "middle",
          "font-family": "IBM Plex Mono, monospace", "font-size": "12", "font-weight": "700", fill: "#FBF8F0",
        });
        texto.innerHTML = "AFASTAMENTOS<tspan x='" + centro[0] + "' dy='16'>CONSOMEM O LOTE</tspan>";
        gAviso.appendChild(texto);
      } else if (d.mancha) {
        /* só a mancha (projeção real, já considerando TO/TP) fica
           desenhada — é a única forma preenchida, e a legenda descreve
           exatamente essa hachura, sem uma 2ª forma (envelope) por trás
           descrevendo outra coisa. */
        gMancha.appendChild(svgEl("path", { d: pathD(d.mancha, tr), fill: "url(#hx-estudo)", "fill-opacity": ".85", stroke: "#14202C", "stroke-width": "1.6" }));
        legenda("leg-mancha", "Projeção máx = " + fmtBR(d.mancha_area) + " m² (limitada por " + d.mancha_limitante + ")");
      } else {
        legenda("leg-mancha", "");
      }

      /* nome da via — único texto de contexto que fica no desenho, além
         da área do lote */
      (d.testadas || []).forEach(function (t) {
        if (!t.rua) return;
        var meio = pontoMedioArestas(d.contorno, t.indices_arestas, n);
        var p0 = d.contorno[t.indices_arestas[0]];
        var p1 = d.contorno[(t.indices_arestas[t.indices_arestas.length - 1] + 1) % n];
        var normal = normalSaida(p0, p1);
        var ancora = tr.pt(meio[0], meio[1]);
        var dirFora = [normal[0] * tr.esc, -normal[1] * tr.esc];
        var alvoVia = pontoNaDirecao(ancora, dirFora, 22);
        var nomeVia = svgEl("text", {
          x: alvoVia[0], y: alvoVia[1], "text-anchor": "middle",
          "font-family": "IBM Plex Mono, monospace", "font-size": "9.5", "font-weight": "600",
          fill: "#14202C", stroke: "#FBF8F0", "stroke-width": "3", "paint-order": "stroke",
        });
        nomeVia.textContent = (t.classificacao ? _rotuloClasseVia(t.classificacao) + " · " : "") + t.rua;
        gCotas.appendChild(nomeVia);
      });

      /* área: caixa de destaque grande, posição fixa (canto sup. esquerdo,
         como na imagem de referência) */
      var gArea = svgEl("g", { class: "area-caixa", transform: "translate(16 16)" });
      gArea.appendChild(svgEl("rect", { width: 112, height: 42 }));
      var rot = svgEl("text", {
        class: "area-rotulo", x: 56, y: 14, "text-anchor": "middle",
        "font-family": "IBM Plex Mono, monospace", "font-size": "8", "letter-spacing": "1",
      });
      rot.textContent = "ÁREA DO LOTE";
      var val = svgEl("text", {
        class: "area-valor", x: 56, y: 32, "text-anchor": "middle",
        "font-family": "IBM Plex Mono, monospace", "font-size": "16",
      });
      val.textContent = fmtBR(d.area_total) + " m²";
      gArea.appendChild(rot); gArea.appendChild(val);
      gCotas.appendChild(gArea);

      var calcTxt;
      if (H < 8) calcTxt = "H < 8,0 m → afast. lateral/fundos mín. 1,50 m (t.4)";
      else if (H <= 12) calcTxt = "8,0 ≤ H ≤ 12,0 m → afast. 2,30 m (t.4)";
      else calcTxt = "2,3 + (" + fmtBR(H, 1) + " − 12) ÷ B(" + est.fator_b + ") = " + fmtBR(d.lateral_m, 2) + " m · B=" + est.fator_b;
      $("est-lat-calc").textContent = calcTxt;

      /* Afastamento Lateral fora do desenho de novo (ficava atrapalhando
         o desenho) — destaque abaixo da caixinha de altura pretendida. */
      var elDestaque = $("est-lat-destaque");
      if (elDestaque) elDestaque.textContent = fmtBR(d.lateral_m, 2);

      if (d.altura_maxima) inH.max = d.altura_maxima;
    }

    function atualizarNumerosEstaticos(area) {
      $("estudo-bas").textContent = est.ca_bas !== null ? fmtBR(area * est.ca_bas) : "—";
      $("estudo-max").textContent = est.ca_max !== null ? fmtBR(area * est.ca_max) : "—";
      $("estudo-un").textContent = est.quota !== null ? "≈ " + fmtBR(Math.floor(area / est.quota)) + " un."
                                  : (est.quota_sem_limite ? "sem limite" : "—");
      $("estudo-tp").textContent = est.tp_pct !== null ? fmtBR(area * est.tp_pct / 100) : "—";
    }

    if (temPoligono) {
      /* ---------- modo real: servidor calcula o envelope geométrico ---------- */
      var ultimaAlturaOk = parseFloat(inH.value);
      var fetchTimer = null;
      /* altura_maxima já veio calculada na carga inicial (varredura
         sequencial, mais cara que os outros cálculos) — manda de volta
         em toda chamada do slider pra o servidor NÃO recalcular isso a
         cada arrastada, só reaproveitar o valor. */
      var alturaMaximaConhecida = est.desenho_inicial.altura_maxima;

      atualizarNumerosEstaticos(est.desenho_inicial.area_total);
      renderizar(est.desenho_inicial, ultimaAlturaOk);

      function pedirAltura(H, aoReceber) {
        fetch("/consulta/estudo", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lat: est.lat, lon: est.lon, altura: H, altura_maxima: alturaMaximaConhecida }),
        }).then(function (r) { return r.json(); }).then(aoReceber).catch(function () {});
      }

      inH.addEventListener("input", function () {
        var H = parseFloat(inH.value);
        $("est-h-out").textContent = fmtBR(H, 1) + " m";
        clearTimeout(fetchTimer);
        fetchTimer = setTimeout(function () {
          pedirAltura(H, function (d) {
            if (d.erro) return;
            /* trava o teto do slider tanto quando os afastamentos já
               consomem o lote inteiro (envelope vazio) quanto quando o
               envelope ainda existe mas não sobra projeção nenhuma pra
               construir (TP + TO já tomaram tudo) — as 2 situações são
               "não dá mais pra subir a altura", mesmo o 2º caso não
               setando d.inconstruivel. Sem isso o slider deixava passar
               de alturas onde a área construível já tinha zerado. */
            var semProjecao = !d.inconstruivel && (!d.mancha || d.mancha_area <= 1);
            if (d.inconstruivel || semProjecao) {
              inH.value = ultimaAlturaOk;
              inH.max = ultimaAlturaOk;
              $("est-h-out").textContent = fmtBR(ultimaAlturaOk, 1) + " m";
              $("est-h-max").textContent = "máx. p/ este lote: " + fmtBR(ultimaAlturaOk, 1) + " m";
              return;
            }
            ultimaAlturaOk = H;
            $("est-h-max").textContent = "";
            renderizar(d, H);
          });
        }, 130);
      });
    } else if (inT && inP) {
      /* ---------- modo manual: retângulo local, sem rede ---------- */
      function retanguloComo(T, P, H) {
        var af = afEfetivo !== null ? afEfetivo : 0;
        var lat = afastLateral(H, est.fator_b);
        var contorno = [[0, 0], [T, 0], [T, P], [0, P], [0, 0]];
        var testadas = [{ rua: "", comprimento_m: T, indices_arestas: [0] }];
        var ew = T - 2 * lat, eh = P - af - lat;
        var inconstruivel = ew <= 0.5 || eh <= 0.5;
        var envelope = inconstruivel ? null : [[lat, af], [T - lat, af], [T - lat, af + eh], [lat, af + eh], [lat, af]];
        var tpM2 = est.tp_pct !== null ? T * P * est.tp_pct / 100 : null;
        var faixaTp = null, faixaTpArea = null;
        if (tpM2 !== null) {
          var vg = Math.min(tpM2 / T, P);
          faixaTp = [[0, 0], [T, 0], [T, vg], [0, vg], [0, 0]];
          faixaTpArea = tpM2;
        }
        var mancha = null, manchaArea = null, limitante = null;
        if (!inconstruivel && est.to_pct !== null) {
          var toM2 = T * P * est.to_pct / 100;
          var profLivre = eh - Math.max(0, (tpM2 !== null ? Math.min(tpM2 / T, P) : 0) - lat);
          var tetoEnv = ew * Math.max(profLivre, 0);
          manchaArea = Math.min(toM2, tetoEnv);
          limitante = toM2 <= tetoEnv ? "TO" : "afastamentos + TP";
          var mh = ew > 0 ? manchaArea / ew : 0;
          var manchaY = af + eh - mh;
          mancha = [[lat, manchaY], [T - lat, manchaY], [T - lat, af + eh], [lat, af + eh], [lat, manchaY]];
        }
        return {
          inconstruivel: inconstruivel, lateral_m: lat, contorno: contorno, testadas: testadas,
          area_total: T * P, envelope: envelope, envelope_area: envelope ? ew * eh : null,
          faixa_tp: faixaTp, faixa_tp_area: faixaTpArea,
          mancha: mancha, mancha_area: manchaArea, mancha_limitante: limitante,
        };
      }
      function atualizarLimiteAltura(T, P) {
        var af = afEfetivo !== null ? afEfetivo : 0;
        var latMax = Math.min((T - 0.5) / 2, P - af - 0.5);
        var hMax;
        if (latMax < 1.5) hMax = null;
        else if (latMax < 2.3) hMax = 7.5;
        else hMax = Math.min(60, 12 + est.fator_b * (latMax - 2.3));
        if (hMax !== null) {
          hMax = Math.floor(hMax * 2) / 2;
          inH.max = hMax; inH.disabled = false;
          if (parseFloat(inH.value) > hMax) inH.value = hMax;
          $("est-h-max").textContent = "máx. p/ este lote: " + fmtBR(hMax, 1) + " m";
        } else {
          inH.disabled = true;
          $("est-h-max").textContent = "afastamentos mínimos não cabem neste lote";
        }
      }
      function redesenharManual() {
        var T = parseFloat(inT.value), P = parseFloat(inP.value);
        if (!T || !P || T <= 0 || P <= 0) return;
        $("est-area").textContent = fmtBR(T * P);
        atualizarLimiteAltura(T, P);
        var H = parseFloat(inH.value);
        atualizarNumerosEstaticos(T * P);
        renderizar(retanguloComo(T, P, H), H);
      }
      inT.addEventListener("input", redesenharManual);
      inP.addEventListener("input", redesenharManual);
      inH.addEventListener("input", redesenharManual);
      redesenharManual();
    }

    /* botão "i" — popover com os disclaimers, fora do fluxo de texto solto */
    var infoBtn = document.getElementById("info-estudo-btn");
    var infoPop = document.getElementById("info-estudo-popover");
    if (infoBtn && infoPop) {
      infoBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        infoPop.hidden = !infoPop.hidden;
      });
      infoPop.querySelectorAll("[data-fechar-info]").forEach(function (el) {
        el.addEventListener("click", function () { infoPop.hidden = true; });
      });
      document.addEventListener("click", function (e) {
        if (!infoPop.hidden && !infoPop.contains(e.target) && e.target !== infoBtn) {
          infoPop.hidden = true;
        }
      });
    }

    /* botão de reportar desenho incorreto */
    var repBtn = document.getElementById("btn-reportar-desenho");
    var repPop = document.getElementById("reportar-popover");
    if (repBtn && repPop) {
      repBtn.addEventListener("click", function () { repPop.hidden = !repPop.hidden; });
      repPop.querySelectorAll("[data-fechar-reportar]").forEach(function (el) {
        el.addEventListener("click", function () { repPop.hidden = true; });
      });
      document.getElementById("reportar-enviar").addEventListener("click", function () {
        var tipo = repPop.querySelector('input[name="reportar-tipo"]:checked').value;
        var comentario = document.getElementById("reportar-comentario").value;
        fetch("/reportar-desenho", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lat: est.lat, lon: est.lon, tipo: tipo, comentario: comentario,
            endereco: document.querySelector(".geocodificado b") ? document.querySelector(".geocodificado b").textContent : null,
          }),
        }).then(function () {
          document.getElementById("reportar-obs").hidden = false;
          document.getElementById("reportar-enviar").disabled = true;
          ga("reportar_desenho", { tipo: tipo });
        }).catch(function () {});
      });
    }
  }

  /* ---------- 7. Exportar ficha (popup visual + impressão) ----------
     Abre no clique de QUALQUER botão de exportar (topo ou rodapé) OU
     sozinho após 1 min navegando na ficha (só uma vez, só se o usuário
     ainda não interagiu com o modal de nenhum jeito). */
  var botoesExport = document.querySelectorAll(".btn-exportar");
  if (botoesExport.length) {
    var modal = document.getElementById("modal-export");
    var interagiu = false;

    function abrirModal() { modal.hidden = false; }
    function fecharModal() { modal.hidden = true; }

    botoesExport.forEach(function (btn) {
      btn.addEventListener("click", function () { interagiu = true; abrirModal(); });
    });
    modal.querySelectorAll("[data-fechar]").forEach(function (el) {
      el.addEventListener("click", function () { interagiu = true; fecharModal(); });
    });
    modal.addEventListener("click", function (e) {
      if (e.target === modal) { interagiu = true; fecharModal(); } /* clique fora da caixa */
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !modal.hidden) { interagiu = true; fecharModal(); }
    });
    document.getElementById("btn-export-confirmar").addEventListener("click", function () {
      interagiu = true;
      ga("exportar_pdf");
      fecharModal();
      setTimeout(function () { window.print(); }, 120);
    });

    /* automático, só se o usuário ainda não interagiu com o modal de nenhum jeito */
    setTimeout(function () {
      if (!interagiu) abrirModal();
    }, 60000);
  }

  /* ---------- 6b. Alternância de aba endereço / índice cadastral ---------- */
  var modosBusca = document.getElementById("modos-busca");
  if (modosBusca) {
    var campoModo = document.getElementById("campo-modo");
    var campoEndereco = document.getElementById("campo-endereco");
    var campoIndice = document.getElementById("campo-indice");
    var dicaBusca = document.getElementById("dica-busca");
    var DICAS = {
      endereco: "Aceita variações de escrita (com ou sem número, bairro, abreviações). Confira sempre o endereço confirmado no carimbo da ficha.",
      indice: "Índice cadastral do IPTU (ex.: no carnê ou no site do SIURBE). Aceita com ou sem espaços."
    };
    modosBusca.querySelectorAll(".modo").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var modo = btn.dataset.modo;
        modosBusca.querySelectorAll(".modo").forEach(function (b) { b.classList.remove("ativo"); });
        btn.classList.add("ativo");
        campoModo.value = modo;
        if (modo === "indice") {
          campoEndereco.hidden = true;
          campoIndice.hidden = false;
          campoIndice.focus();
        } else {
          campoIndice.hidden = true;
          campoEndereco.hidden = false;
          campoEndereco.focus();
        }
        dicaBusca.textContent = DICAS[modo];
      });
    });
  }

  /* ---------- 6c. Estado de carregamento no submit da busca ----------
     O POST recarrega a página; o esqueleto fica visível na página atual
     enquanto o servidor responde (essencial no cold-start do Render). */
  var formBusca = document.getElementById("form-busca");
  var skeleton = document.getElementById("skeleton-carregando");
  if (formBusca && skeleton) {
    formBusca.addEventListener("submit", function (e) {
      var modo = document.getElementById("campo-modo").value;
      var campo = modo === "indice"
        ? document.getElementById("campo-indice")
        : document.getElementById("campo-endereco");
      if (!campo || !campo.value.trim()) return;  // deixa o navegador validar vazio
      // esconde ficha/erro antigos e mostra o esqueleto
      var fichaAntiga = document.querySelector(".ficha");
      if (fichaAntiga) fichaAntiga.style.display = "none";
      var erroAntigo = document.querySelector(".erro");
      if (erroAntigo) erroAntigo.style.display = "none";
      skeleton.hidden = false;
      skeleton.setAttribute("aria-hidden", "false");
      skeleton.scrollIntoView({ behavior: "smooth", block: "nearest" });
      var btn = formBusca.querySelector('button[type="submit"]');
      if (btn) { btn.disabled = true; btn.textContent = "Consultando…"; }
    });
  }

  /* ---------- 4c. Carrossel "A ficha" — cicla sozinho, clique assume ---------- */
  var fcEl = document.getElementById("ficha-carrossel");
  if (fcEl) {
    var fcDados = JSON.parse(document.getElementById("dados-fc").textContent);
    var fcItensWrap = document.getElementById("fc-itens");
    var fcFoco = document.querySelector(".fc-foco");
    var fcNum = document.getElementById("fc-num");
    var fcTitulo = document.getElementById("fc-titulo");
    var fcTexto = document.getElementById("fc-texto");
    var fcBotoes = [];

    fcDados.forEach(function (item, i) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "fc-item" + (i === 0 ? " ativo" : "");
      btn.innerHTML = '<span class="fc-item-num mono">0' + (i + 1) + '</span><span class="fc-item-t">' + item.t + "</span>";
      btn.addEventListener("click", function () { irPara(i, true); });
      fcItensWrap.appendChild(btn);
      fcBotoes.push(btn);
    });

    var fcIdx = 0, fcTimer = null;
    function irPara(i, doClique) {
      fcIdx = i;
      if (reduzMovimento) {
        aplicar();
      } else {
        fcFoco.classList.add("trocando");
        setTimeout(function () { aplicar(); fcFoco.classList.remove("trocando"); }, 220);
      }
      fcBotoes.forEach(function (b, j) { b.classList.toggle("ativo", j === i); });
      if (doClique) reiniciarCiclo();
    }
    function aplicar() {
      var item = fcDados[fcIdx];
      fcNum.textContent = "0" + (fcIdx + 1);
      fcTitulo.textContent = item.t;
      fcTexto.textContent = item.d;
    }
    function proximo() { irPara((fcIdx + 1) % fcDados.length, false); }
    function reiniciarCiclo() {
      if (fcTimer) clearInterval(fcTimer);
      /* o ciclo roda mesmo com "reduzir movimento" (é troca de conteúdo,
         não animação) — só a transição de fade é que se desliga, igual
         padrão já usado no mapa vivo do hero */
      fcTimer = setInterval(proximo, 4200);
    }

    aplicar();
    reiniciarCiclo();
  }

  /* ---------- 5. Placeholder que digita endereços reais ---------- */
  var campo = document.getElementById("busca-input");
  if (campo && !reduzMovimento) {
    var exemplos = [
      "Praça da Liberdade",
      "Av. Otacílio Negrão de Lima, 1000",
      "Rua Fernandes Tourinho, 200",
      "Rua da Bahia, 1200"
    ];
    var iEx = 0, iCh = 0, apagando = false, pausado = false;

    campo.addEventListener("focus", function () { pausado = true; campo.placeholder = "Digite um endereço em BH"; });
    campo.addEventListener("blur", function () { if (!campo.value) pausado = false; });

    function tique() {
      if (!pausado && !campo.value) {
        var atual = exemplos[iEx];
        if (!apagando) {
          iCh++;
          campo.placeholder = atual.slice(0, iCh);
          if (iCh === atual.length) { apagando = true; setTimeout(tique, 1600); return; }
        } else {
          iCh--;
          campo.placeholder = atual.slice(0, iCh) || " ";
          if (iCh === 0) { apagando = false; iEx = (iEx + 1) % exemplos.length; }
        }
      }
      setTimeout(tique, apagando ? 34 : 74);
    }
    setTimeout(tique, 900);
  }
})();
