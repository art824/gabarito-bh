/* Mapa do lote no topo da ficha (Fase 1 do plano, docs/visao_e_plano.md).

   Como funciona, em uma frase: o fundo (ruas, quadras, nomes) vem de um
   serviço de mapas gratuito e sem chave (OpenFreeMap, dados do OpenStreetMap);
   por cima, desenhamos o contorno OFICIAL do lote e dos vizinhos (Cadastro
   Técnico da Prefeitura), que o nosso servidor manda pela rota /consulta/mapa.

   Regra: o mapa é um enfeite útil, nunca uma dependência. Se a biblioteca,
   o fundo ou a rota falharem, o bloco some e a ficha continua igual. */
(function () {
  "use strict";

  var el = document.getElementById("mapa-lote");
  if (!el) return;

  var LIB_JS = "/static/vendor/maplibre-gl.js?v=4.7.1";
  var LIB_CSS = "/static/vendor/maplibre-gl.css?v=4.7.1";
  var ESTILO = "https://tiles.openfreemap.org/styles/positron";

  var lat = parseFloat(el.getAttribute("data-lat"));
  var lon = parseFloat(el.getAttribute("data-lon"));
  if (!isFinite(lat) || !isFinite(lon)) return desistir("coordenadas ausentes");

  var tempoLimite = setTimeout(function () { desistir("tempo esgotado"); }, 15000);
  var desistiu = false;

  function desistir(motivo) {
    if (desistiu) return;
    desistiu = true;
    clearTimeout(tempoLimite);
    // com o desenho imediato (SVG) na tela, o bloco FICA: vira um mapa estático
    if (!el.querySelector(".mapa-placeholder")) el.classList.add("mapa-falhou");
    if (window.console) console.warn("[mapa] não exibido:", motivo);
  }

  function carregarCss(href) {
    var l = document.createElement("link");
    l.rel = "stylesheet"; l.href = href; l.crossOrigin = "anonymous";
    document.head.appendChild(l);
  }

  function carregarJs(src, ok, erro) {
    var s = document.createElement("script");
    s.src = src; s.async = true; s.crossOrigin = "anonymous";
    s.onload = ok; s.onerror = erro;
    document.head.appendChild(s);
  }

  /* caixa que envolve todas as coordenadas de uma geometria GeoJSON */
  function estenderCaixa(caixa, coords) {
    if (typeof coords[0] === "number") {
      caixa[0] = Math.min(caixa[0], coords[0]); caixa[1] = Math.min(caixa[1], coords[1]);
      caixa[2] = Math.max(caixa[2], coords[0]); caixa[3] = Math.max(caixa[3], coords[1]);
      return;
    }
    for (var i = 0; i < coords.length; i++) estenderCaixa(caixa, coords[i]);
  }

  /* o fundo "positron" é cinza-frio; aproxima do papel e da tinta do site */
  function aquecerFundo(map) {
    var estilo = map.getStyle();
    (estilo.layers || []).forEach(function (camada) {
      try {
        if (camada.type === "background") {
          map.setPaintProperty(camada.id, "background-color", "#F2EDE0");
        } else if (camada.type === "fill" && /water/.test(camada.id)) {
          map.setPaintProperty(camada.id, "fill-color", "#D6DCD8");
        } else if (camada.type === "fill" && /landuse|park|landcover/.test(camada.id)) {
          map.setPaintProperty(camada.id, "fill-opacity", 0.35);
        } else if (camada.type === "fill" && /building/.test(camada.id)) {
          map.setPaintProperty(camada.id, "fill-color", "#E4DDCB");
        } else if (camada.type === "symbol") {
          map.setPaintProperty(camada.id, "text-color", "#5C584C");
        }
      } catch (e) { /* camada sem essa propriedade: ignora */ }
    });
  }

  /* Desenho imediato do lote (SVG) assim que os dados chegam, antes de a
     biblioteca e o fundo carregarem: a pessoa nunca vê um espaço vazio. Sai
     de cena quando o mapa real estiver pronto. */
  function placeholder(dados) {
    var fs = dados.features || [];
    var caixa = [Infinity, Infinity, -Infinity, -Infinity];
    fs.forEach(function (f) { estenderCaixa(caixa, f.geometry.coordinates); });
    if (!isFinite(caixa[0])) return null;
    var k = Math.cos(lat * Math.PI / 180);
    var w = (caixa[2] - caixa[0]) * k, h = caixa[3] - caixa[1];
    var NS = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("class", "mapa-placeholder");
    svg.setAttribute("viewBox", "0 0 " + (w * 1e5).toFixed(0) + " " + (h * 1e5).toFixed(0));
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
    function anel(c) {
      return "M" + c.map(function (p) {
        return ((p[0] - caixa[0]) * k * 1e5).toFixed(0) + " " + ((caixa[3] - p[1]) * 1e5).toFixed(0);
      }).join("L") + "Z";
    }
    fs.forEach(function (f) {
      var g = f.geometry, partes = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
      var path = document.createElementNS(NS, "path");
      path.setAttribute("d", partes.map(function (poly) { return poly.map(anel).join(""); }).join(""));
      var lote = f.properties.papel === "lote";
      path.setAttribute("fill", lote ? "rgba(176,64,44,.42)" : "none");
      path.setAttribute("stroke", lote ? "#B0402C" : "#6E6858");
      path.setAttribute("stroke-width", lote ? "260" : "90");
      svg.appendChild(path);
    });
    el.insertBefore(svg, el.firstChild);
    el.classList.add("mapa-pronto");
    return svg;
  }

  function montar(dados) {
    var toque = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
    var map;
    try {
      map = new maplibregl.Map({
        container: el,
        style: ESTILO,
        center: [lon, lat],
        zoom: 17.2,
        // crédito próprio na legenda (sempre visível, uma linha): o do MapLibre
        // se abria sozinho e cobria a faixa do mapa no celular
        attributionControl: false,
        // mapa QUASE PARADO (pedido do Arthur): nada de arrastar, girar ou pinçar;
        // só os botões + e − (zoom). A página rola normalmente por cima dele.
        interactive: true, scrollZoom: false, dragPan: false, dragRotate: false,
        touchZoomRotate: false, doubleClickZoom: false, boxZoom: false, keyboard: false,
        touchPitch: false, pitchWithRotate: false,
        maxZoom: 19.5, minZoom: 15
      });
    } catch (e) { return desistir("WebGL indisponível"); }

    var montado = false;
    map.on("error", function (ev) {
      // erro de um ladrilho isolado não derruba o mapa; só desiste se o estilo nem chegou
      if (!montado) desistir(ev && ev.error ? ev.error.message : "erro no fundo");
    });

    // "style.load" (e não "load"): "load" espera TODOS os ladrilhos do fundo, o
    // que levou >4 s no teste de celular. Aqui o lote aparece logo e as ruas
    // vão preenchendo por trás.
    map.once("style.load", function () {
      if (desistiu) return;
      montado = true;
      aquecerFundo(map);
      map.addSource("ctm", { type: "geojson", data: dados });

      map.addLayer({ id: "vizinhos-linha", type: "line", source: "ctm",
        filter: ["==", ["get", "papel"], "vizinho"],
        paint: { "line-color": "#6E6858", "line-width": 0.8, "line-opacity": 0.75 } });
      map.addLayer({ id: "lote-preenchimento", type: "fill", source: "ctm",
        filter: ["==", ["get", "papel"], "lote"],
        paint: { "fill-color": "#B0402C", "fill-opacity": 0.42 } });
      map.addLayer({ id: "lote-contorno", type: "line", source: "ctm",
        filter: ["==", ["get", "papel"], "lote"],
        paint: { "line-color": "#B0402C", "line-width": 2.4 } });

      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

      // enquadra o lote no meio da faixa visível (a máscara apaga as bordas)
      var lote = (dados.features || []).filter(function (f) { return f.properties.papel === "lote"; })[0];
      if (lote) {
        var caixa = [Infinity, Infinity, -Infinity, -Infinity];
        estenderCaixa(caixa, lote.geometry.coordinates);
        // a busca cobre o topo do mapa e a ficha cobre o pé (margens negativas
        // no CSS, mais os 40 px de margem da ficha): o lote vai pro meio do resto
        var cs = getComputedStyle(el);
        var cobertoTopo = Math.max(0, -parseFloat(cs.marginTop) || 0);
        var cobertoPe = Math.max(0, -parseFloat(cs.marginBottom) || 0) + 40;
        var largura = el.clientWidth;
        var lado = Math.max(40, Math.round(largura / 2 - 160));
        map.fitBounds([[caixa[0], caixa[1]], [caixa[2], caixa[3]]], {
          padding: { top: cobertoTopo + 24, bottom: cobertoPe + 24, left: lado, right: lado },
          maxZoom: 18.6, duration: 0
        });
      } else {
        // lote não identificado: marca só o ponto pesquisado
        new maplibregl.Marker({ color: "#B0402C" }).setLngLat([lon, lat]).addTo(map);
      }

      // mostra já: o fundo continua chegando em pedaços, mas o lote já está
      // desenhado. (Esperar o "idle" levava vários segundos no celular.)
      clearTimeout(tempoLimite);
      el.classList.add("mapa-pronto");
      var ph = el.querySelector(".mapa-placeholder");
      if (ph) ph.parentNode.removeChild(ph);
    });
  }

  carregarCss(LIB_CSS);
  var dadosPromessa = fetch("/consulta/mapa?lat=" + lat.toFixed(6) + "&lon=" + lon.toFixed(6))
    .then(function (r) { if (!r.ok) throw new Error("rota do mapa: " + r.status); return r.json(); })
    .then(function (d) { if (!desistiu) placeholder(d); return d; });

  carregarJs(LIB_JS, function () {
    if (!window.maplibregl) return desistir("biblioteca não carregou");
    dadosPromessa.then(montar).catch(function (e) { desistir(e.message); });
  }, function () { desistir("biblioteca não carregou"); });
})();
