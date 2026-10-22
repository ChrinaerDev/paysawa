(function () {
  "use strict";
  var D = window.DOCS || { langs: { en: { groups: [] } }, code: {}, baseUrl: "", version: "" };
  var KEYS = { base: "paysawa_docs_base", code: "paysawa_docs_code", theme: "paysawa_docs_theme", ui: "paysawa_docs_lang" };

  var UI = {
    en: {
      search: "Search the docs", base: "API base URL", docs: "Docs", example_request: "Example request", example_response: "Example response",
      headers: "Headers", params: "Parameters", body_params: "Body parameters", name: "Name", type: "Type", required: "Required", optional: "optional",
      required_badge: "required", previous: "Previous", next: "Next", nothing: "Nothing found for", copy: "Copy", copied: "Copied",
      auth_none: "No authentication needed.",
      auth_token: 'Send <code>Authorization: Token &lt;token&gt;</code>. Get the token with <a href="#/token">{token}</a>.',
      auth_apikey: "Send your secret key: <code>Authorization: Bearer sk_test_...</code> (or <code>sk_live_...</code>).",
      theme: "Switch light/dark theme", language: "Language", menu: "Menu", other: "FR", suffix: "Paysawa docs"
    },
    fr: {
      search: "Rechercher dans la documentation", base: "URL de base de l'API", docs: "Docs", example_request: "Exemple de requête", example_response: "Exemple de réponse",
      headers: "En-têtes", params: "Paramètres", body_params: "Paramètres du corps", name: "Nom", type: "Type", required: "Obligatoire", optional: "facultatif",
      required_badge: "obligatoire", previous: "Précédent", next: "Suivant", nothing: "Aucun résultat pour", copy: "Copier", copied: "Copié",
      auth_none: "Aucune authentification nécessaire.",
      auth_token: 'Envoyez <code>Authorization: Token &lt;jeton&gt;</code>. Obtenez le jeton avec <a href="#/token">{token}</a>.',
      auth_apikey: "Envoyez votre clé secrète : <code>Authorization: Bearer sk_test_...</code> (ou <code>sk_live_...</code>).",
      theme: "Basculer entre thème clair et sombre", language: "Langue", menu: "Menu", other: "EN", suffix: "Documentation Paysawa"
    }
  };

  var state = { base: D.baseUrl, code: "curl", ui: "en", resp: {}, query: "", id: null };
  var groups = [], byId = {}, order = [];

  // ---------------------------------------------------------------- helpers
  function t(key) { return (UI[state.ui] && UI[state.ui][key]) || UI.en[key] || key; }
  function useLang(lang) {
    state.ui = D.langs[lang] ? lang : "en";
    groups = D.langs[state.ui].groups; byId = {}; order = [];
    groups.forEach(function (g) { g.items.forEach(function (i) { byId[i.id] = i; order.push(i.id); }); });
  }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function escCode(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function lsGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} }
  function cleanBase(v) { return String(v || "").trim().replace(/\/+$/, ""); }
  function swap(text) { return String(text).split("{{BASE_URL}}").join(state.base); }

  // JSON highlighting on text that is already HTML-escaped (quotes are NOT escaped inside code blocks)
  function highlight(escaped, lang) {
    if (lang !== "json") return escaped;
    return escaped.replace(/("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\b\d+(?:\.\d+)?\b/g, function (m, str, colon, lit) {
      if (str) return colon ? '<span class="tk-key">' + str + "</span>" + colon : '<span class="tk-str">' + str + "</span>";
      if (lit) return '<span class="tk-lit">' + m + "</span>";
      return '<span class="tk-num">' + m + "</span>";
    });
  }
  function copyButton() { return '<button class="copy" type="button" data-copy="1">' + esc(t("copy")) + "</button>"; }
  function codeBox(code, lang) {
    return '<div class="codebox">' + copyButton() + '<pre class="code" data-lang="' + esc(lang) + '"><code>' + highlight(escCode(swap(code)), lang) + "</code></pre></div>";
  }
  // prose pages carry pre-escaped <pre class="code"> blocks: put the base URL in, highlight JSON, add the copy button
  function prose(html) {
    return html.split("{{BASE_URL}}").join(esc(state.base)).replace(/<pre class="code" data-lang="([^"]*)"><code>([\s\S]*?)<\/code><\/pre>/g, function (m, lang, inner) {
      return '<div class="codebox">' + copyButton() + '<pre class="code" data-lang="' + lang + '"><code>' + highlight(inner, lang) + "</code></pre></div>";
    });
  }

  // ---------------------------------------------------------------- rendering (pure functions returning HTML)
  function filterItems(query) {
    var q = (query || "").trim().toLowerCase(), out = [];
    groups.forEach(function (g) {
      g.items.forEach(function (i) {
        if (!q || i.title.toLowerCase().indexOf(q) >= 0 || (i.text || "").toLowerCase().indexOf(q) >= 0 || (i.path || "").toLowerCase().indexOf(q) >= 0) out.push(i);
      });
    });
    return out;
  }

  function renderSidebar(active, query) {
    var hits = filterItems(query), html = "";
    groups.forEach(function (g) {
      var items = g.items.filter(function (i) { return hits.indexOf(i) >= 0; });
      if (!items.length) return;
      html += '<div class="nav-group"><div class="nav-title">' + esc(g.title) + "</div>";
      items.forEach(function (i) {
        html += '<a class="nav-item' + (i.id === active ? " active" : "") + '" href="#/' + esc(i.id) + '">' +
          (i.kind === "endpoint" ? '<span class="m m-' + esc(i.method.toLowerCase()) + '">' + esc(i.method) + "</span>" : "") + "<span>" + esc(i.title) + "</span></a>";
      });
      html += "</div>";
    });
    return html || '<div class="nav-empty">' + esc(t("nothing")) + " &ldquo;" + esc(query) + "&rdquo;</div>";
  }

  function pager(id) {
    var n = order.indexOf(id), prev = byId[order[n - 1]], next = byId[order[n + 1]], html = '<div class="pager">';
    html += prev ? '<a class="prev" href="#/' + esc(prev.id) + '"><small>' + esc(t("previous")) + "</small>" + esc(prev.title) + "</a>" : "<span></span>";
    html += next ? '<a class="next" href="#/' + esc(next.id) + '"><small>' + esc(t("next")) + "</small>" + esc(next.title) + "</a>" : "<span></span>";
    return html + "</div>";
  }

  function paramTable(title, rows) {
    if (!rows || !rows.length) return "";
    var html = "<h3>" + esc(title) + '</h3><div class="table-wrap"><table><thead><tr><th>' + esc(t("name")) + "</th><th>" + esc(t("type")) + "</th><th>" +
      esc(t("required")) + "</th><th>Description</th></tr></thead><tbody>";
    rows.forEach(function (r) {
      html += "<tr><td><code>" + esc(r.name) + "</code></td><td>" + esc(r.type) + "</td><td>" +
        (r.required ? '<span class="req">' + esc(t("required_badge")) + "</span>" : esc(t("optional"))) + "</td><td>" + prose(r.descriptionHtml || esc(r.description || "")) + "</td></tr>";
    });
    return html + "</tbody></table></div>";
  }

  function authLine(kind) {
    var tokenTitle = byId.token ? byId.token.title : "token";
    if (kind === "token") return '<div class="auth">' + t("auth_token").replace("{token}", esc(tokenTitle)) + "</div>";
    if (kind === "apikey") return '<div class="auth">' + t("auth_apikey") + "</div>";
    return '<div class="auth">' + esc(t("auth_none")) + "</div>";
  }

  function renderEndpoint(item) {
    var cd = D.code[item.id], ex = cd.examples, current = ex.filter(function (e) { return e.lang === state.code; })[0] || ex[0];
    var ri = Math.min(state.resp[item.id] || 0, cd.responses.length - 1), resp = cd.responses[ri];
    var html = '<article class="doc endpoint"><div class="ep-grid"><div class="ep-main">';
    html += '<div class="ep-head"><span class="m m-' + esc(item.method.toLowerCase()) + '">' + esc(item.method) + '</span><code class="ep-path">' + esc(item.path) + "</code></div>";
    html += "<h1>" + esc(item.title) + '</h1><p class="lead">' + prose(item.summary) + "</p>" + prose(item.descriptionHtml || "") + authLine(item.auth);
    html += paramTable(t("headers"), item.headers) + paramTable(item.method === "GET" ? t("params") : t("body_params"), item.params);
    if (item.notesHtml) html += '<div class="notes">' + prose(item.notesHtml) + "</div>";
    html += '</div><aside class="ep-side"><div class="panel"><div class="panel-title">' + esc(t("example_request")) + '</div><div class="tabs">';
    ex.forEach(function (e) { html += '<button type="button" data-code="' + esc(e.lang) + '" class="' + (e === current ? "on" : "") + '">' + esc(e.label) + "</button>"; });
    html += "</div>" + codeBox(current.code, current.lang === "curl" ? "bash" : current.lang === "javascript" ? "javascript" : "python") + "</div>";
    html += '<div class="panel"><div class="panel-title">' + esc(t("example_response")) + '</div><div class="tabs">';
    cd.responses.forEach(function (r, n) {
      html += '<button type="button" data-resp="' + n + '" data-item="' + esc(item.id) + '" class="' + (n === ri ? "on" : "") + '"><span class="status ' +
        (r.status < 400 ? "s-ok" : "s-err") + '">' + r.status + "</span>" + esc((item.responseTitles || [])[n] || "") + "</button>";
    });
    html += "</div>" + codeBox(resp.code, "json") + "</div></aside></div>" + pager(item.id) + "</article>";
    return html;
  }

  function renderPage(item) { return '<article class="doc page">' + prose(item.html) + pager(item.id) + "</article>"; }
  function renderItem(item) { return item.kind === "endpoint" ? renderEndpoint(item) : renderPage(item); }

  // ---------------------------------------------------------------- DOM wiring
  var el = {};
  function currentId() {
    var m = /^#\/([a-z0-9-]+)/.exec(window.location.hash || "");
    return m && byId[m[1]] ? m[1] : order[0];
  }
  function drawSidebar() { el.nav.innerHTML = renderSidebar(state.id, state.query); }
  function route() {
    state.id = currentId();
    var item = byId[state.id];
    el.content.innerHTML = renderItem(item);
    drawSidebar();
    window.document.title = item.title + " | " + t("suffix");
    if (window.scrollTo) window.scrollTo(0, 0);
    if (window.document.body) window.document.body.classList.remove("nav-open");
  }
  function applyUi() {
    var d = window.document;
    d.documentElement.lang = state.ui;
    el.search.placeholder = t("search"); el.search.setAttribute("aria-label", t("search"));
    el.baseLabel.textContent = t("base"); el.baseInput.setAttribute("aria-label", t("base"));
    el.brandSub.textContent = t("docs");
    el.langBtn.textContent = t("other"); el.langBtn.setAttribute("aria-label", t("language"));
    el.themeBtn.setAttribute("aria-label", t("theme")); el.menuBtn.setAttribute("aria-label", t("menu"));
  }
  function setLang(lang) { useLang(lang); lsSet(KEYS.ui, state.ui); applyUi(); route(); }

  function copyText(text, button) {
    function done() { button.textContent = t("copied"); setTimeout(function () { button.textContent = t("copy"); }, 1200); }
    if (window.navigator && window.navigator.clipboard) { window.navigator.clipboard.writeText(text).then(done, done); return; }
    var ta = window.document.createElement("textarea"); ta.value = text; window.document.body.appendChild(ta); ta.select();
    try { window.document.execCommand("copy"); } catch (e) {} window.document.body.removeChild(ta); done();
  }
  function onClick(ev) {
    var target = ev.target && ev.target.closest ? ev.target : null;
    if (!target) return;
    var tab = target.closest("[data-code]");
    if (tab) { state.code = tab.getAttribute("data-code"); lsSet(KEYS.code, state.code); route(); return; }
    var rb = target.closest("[data-resp]");
    if (rb) { state.resp[rb.getAttribute("data-item")] = Number(rb.getAttribute("data-resp")); route(); return; }
    var cp = target.closest("[data-copy]");
    if (cp) { var code = cp.parentNode.querySelector("code"); if (code) copyText(code.textContent, cp); }
  }

  function init() {
    var d = window.document;
    ["nav", "content", "search", "base-input", "base-label", "brand-sub", "lang-btn", "theme-btn", "menu-btn", "version", "scrim"].forEach(function (id) {
      el[id.replace(/-([a-z])/g, function (m, c) { return c.toUpperCase(); })] = d.getElementById(id);
    });
    var saved = lsGet(KEYS.ui), nav = window.navigator || {};
    useLang(saved || (/^fr/i.test(nav.language || "") ? "fr" : "en"));
    if (/YOUR-PAYSAWA-URL/.test(D.baseUrl || "") && /^https?:\/\//.test(window.location.origin || "")) D.baseUrl = window.location.origin;  // served by Paysawa itself
    state.base = cleanBase(lsGet(KEYS.base)) || D.baseUrl;
    state.code = lsGet(KEYS.code) || "curl";
    var theme = lsGet(KEYS.theme); if (theme) d.documentElement.setAttribute("data-theme", theme);
    el.baseInput.value = state.base;
    el.version.textContent = D.version ? "v" + D.version : "";
    applyUi();

    el.baseInput.addEventListener("input", function (e) { state.base = cleanBase(e.target.value) || D.baseUrl; lsSet(KEYS.base, cleanBase(e.target.value)); route(); });
    el.search.addEventListener("input", function (e) { state.query = e.target.value; drawSidebar(); });
    el.search.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { var hits = filterItems(state.query); if (hits.length) window.location.hash = "#/" + hits[0].id; }
    });
    el.langBtn.addEventListener("click", function () { setLang(state.ui === "en" ? "fr" : "en"); });
    el.themeBtn.addEventListener("click", function () {
      var cur = d.documentElement.getAttribute("data-theme");
      var dark = cur === "dark" || (!cur && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
      var next = dark ? "light" : "dark"; d.documentElement.setAttribute("data-theme", next); lsSet(KEYS.theme, next);
    });
    el.menuBtn.addEventListener("click", function () { d.body.classList.toggle("nav-open"); });
    if (el.scrim) el.scrim.addEventListener("click", function () { d.body.classList.remove("nav-open"); });
    d.addEventListener("click", onClick);
    window.addEventListener("hashchange", route);
    route();
  }

  useLang("en");
  window.PaysawaDocs = { state: state, t: t, esc: esc, filterItems: filterItems, renderSidebar: renderSidebar, renderItem: renderItem, renderPage: renderPage,
                         renderEndpoint: renderEndpoint, highlight: highlight, cleanBase: cleanBase, useLang: useLang, init: init, route: route, ui: UI };
  if (window.document && window.document.getElementById && window.document.getElementById("content")) init();
})();
