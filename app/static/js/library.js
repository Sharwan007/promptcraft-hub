/* Prompt Library: debounced search, live filtering without a full reload, grid/list toggle, suggestions. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var form = document.getElementById("filter-form"), results = document.getElementById("results");
  if (!form || !results) return;
  var qInput = document.getElementById("q"), viewInput = document.getElementById("f-view"), count = document.getElementById("result-count");
  var controller = null;

  function params(extra) {
    var p = new URLSearchParams();
    new FormData(form).forEach(function (v, k) { if (String(v).trim() !== "") p.set(k, String(v).trim()); });
    if (p.get("sort") === "relevance") p.delete("sort");
    Object.keys(extra || {}).forEach(function (k) { p.set(k, extra[k]); });
    return p;
  }

  function load(page, push) {
    var p = params(page > 1 ? { page: page } : {});
    var qs = p.toString();
    if (controller) controller.abort();
    controller = new AbortController();
    results.classList.add("loading");
    results.setAttribute("aria-busy", "true");
    p.set("partial", "1");
    fetch("/prompts?" + p.toString(), { signal: controller.signal, credentials: "same-origin", headers: { "Accept": "text/html" } })
      .then(function (r) { if (!r.ok) throw new Error("bad status"); return r.text(); })
      .then(function (html) {
        results.innerHTML = html;
        var meta = document.getElementById("results-meta");
        if (meta && count) {
          var t = Number(meta.dataset.total), pg = Number(meta.dataset.page), pages = Number(meta.dataset.pages), q = qInput.value.trim();
          count.innerHTML = "<strong>" + t + "</strong> prompt" + (t === 1 ? "" : "s") + " found" + (q ? " for &ldquo;" + PCH.escape(q) + "&rdquo;" : "") + (pages > 1 ? " &middot; page " + pg + " of " + pages : "");
        }
        if (push !== false) history.pushState(null, "", "/prompts" + (qs ? "?" + qs : ""));
        bindPagination();
      })
      .catch(function (e) { if (e.name !== "AbortError") { PCH.toast("The results could not be refreshed. Reloading the page.", "error"); window.location.href = "/prompts" + (qs ? "?" + qs : ""); } })
      .then(function () { results.classList.remove("loading"); results.removeAttribute("aria-busy"); });
  }

  function bindPagination() {
    results.querySelectorAll(".pagination a").forEach(function (a) {
      a.addEventListener("click", function (e) {
        var u = new URL(a.href); var pg = Number(u.searchParams.get("page") || 1);
        e.preventDefault(); load(pg); window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
  }

  var live = PCH.debounce(function () { load(1); }, 300);
  form.addEventListener("submit", function (e) { e.preventDefault(); load(1); });
  qInput.addEventListener("input", live);
  form.querySelectorAll("select, input[type=checkbox], #f-tag").forEach(function (el) { el.addEventListener("change", function () { load(1); }); });

  /* subcategory list follows the chosen category */
  var cat = document.getElementById("f-category"), sub = document.getElementById("f-sub");
  function syncSubs() {
    var slug = cat.value;
    Array.prototype.forEach.call(sub.options, function (o) { if (!o.value) return; o.hidden = !!slug && o.dataset.category !== slug; if (o.hidden && o.selected) sub.value = ""; });
  }
  cat.addEventListener("change", syncSubs); syncSubs();

  /* typed suggestions in the datalist */
  qInput.addEventListener("input", PCH.debounce(function () {
    var q = qInput.value.trim(); if (q.length < 2) return;
    PCH.get("/api/search/suggestions?q=" + encodeURIComponent(q)).then(function (r) {
      var dl = document.getElementById("q-suggestions"); dl.innerHTML = "";
      (r.suggestions || []).filter(function (s) { return s.type === "prompt"; }).forEach(function (s) { var o = document.createElement("option"); o.value = s.label; dl.appendChild(o); });
    }, function () { /* suggestions are optional */ });
  }, 250));

  /* grid / list */
  document.querySelectorAll("[data-view]").forEach(function (b) {
    b.addEventListener("click", function () {
      viewInput.value = b.dataset.view;
      document.querySelectorAll("[data-view]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      load(1);
    });
  });

  document.getElementById("clear-filters").addEventListener("click", function (e) {
    e.preventDefault(); form.reset(); qInput.value = ""; Array.prototype.forEach.call(form.elements, function (el) {
      if (el.tagName === "SELECT") el.selectedIndex = 0; else if (el.type === "checkbox") el.checked = false; else if (el.type !== "hidden" && el.type !== "submit") el.value = "";
    });
    syncSubs(); load(1);
  });

  var toggle = document.getElementById("filter-toggle"), panel = document.getElementById("filters");
  if (toggle) toggle.addEventListener("click", function () { var open = panel.classList.toggle("is-open"); toggle.setAttribute("aria-expanded", open ? "true" : "false"); });

  window.addEventListener("popstate", function () { window.location.reload(); });
  bindPagination();
})();
