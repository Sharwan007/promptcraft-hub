/* Application shell: theme, sidebar, drawer, global search, dropdowns, copy buttons, shortcuts. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var app = document.getElementById("app");

  /* ---- Theme -------------------------------------------------------- */
  var themeBtn = document.getElementById("theme-toggle");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("pch-theme", next); } catch (e) { /* ignore */ }
    PCH.toast(next === "dark" ? "Dark mode on." : "Light mode on.", "info", 1800);
  });

  /* ---- Sidebar (desktop collapse, mobile drawer) -------------------- */
  try { if (localStorage.getItem("pch-sidebar") === "collapsed") app.classList.add("is-collapsed"); } catch (e) { /* ignore */ }
  var collapse = document.getElementById("collapse-toggle");
  if (collapse) collapse.addEventListener("click", function () {
    app.classList.toggle("is-collapsed");
    try { localStorage.setItem("pch-sidebar", app.classList.contains("is-collapsed") ? "collapsed" : "open"); } catch (e) { /* ignore */ }
  });
  var menu = document.getElementById("menu-toggle");
  function setDrawer(open) {
    app.classList.toggle("drawer-open", open);
    if (menu) menu.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) { var first = document.querySelector("#sidebar .nav a"); if (first) first.focus(); } else if (menu) { menu.focus(); }
  }
  if (menu) menu.addEventListener("click", function () { setDrawer(!app.classList.contains("drawer-open")); });
  document.querySelectorAll("[data-drawer-close]").forEach(function (el) { el.addEventListener("click", function () { setDrawer(false); }); });
  document.querySelectorAll("#sidebar .nav a").forEach(function (a) { a.addEventListener("click", function () { app.classList.remove("drawer-open"); }); });

  /* ---- Global search with suggestions ------------------------------- */
  var form = document.querySelector(".global-search");
  if (form) {
    var input = form.querySelector("input"), box = document.getElementById("global-suggest"), idx = -1, items = [];
    var close = function () { box.hidden = true; input.setAttribute("aria-expanded", "false"); idx = -1; };
    var render = function (list) {
      items = list; box.innerHTML = "";
      if (!list.length) { close(); return; }
      list.forEach(function (s, i) {
        var a = PCH.el("a", { href: s.url, role: "option", id: "sug-" + i, "aria-selected": "false" });
        a.appendChild(PCH.el("span", { text: s.label })); a.appendChild(PCH.el("span", { "class": "kind", text: s.type }));
        box.appendChild(a);
      });
      box.hidden = false; input.setAttribute("aria-expanded", "true");
    };
    var fetchSuggestions = PCH.debounce(function () {
      var q = input.value.trim();
      if (q.length < 2) { close(); return; }
      PCH.get("/api/search/suggestions?q=" + encodeURIComponent(q)).then(function (r) { render(r.suggestions || []); }, close);
    }, 220);
    input.addEventListener("input", fetchSuggestions);
    input.addEventListener("keydown", function (e) {
      var links = box.querySelectorAll("a");
      if (e.key === "ArrowDown" && links.length) { e.preventDefault(); idx = (idx + 1) % links.length; }
      else if (e.key === "ArrowUp" && links.length) { e.preventDefault(); idx = (idx - 1 + links.length) % links.length; }
      else if (e.key === "Escape") { close(); return; }
      else if (e.key === "Enter" && idx >= 0 && links[idx]) { e.preventDefault(); window.location.href = links[idx].href; return; }
      else { return; }
      links.forEach(function (l, i) { l.setAttribute("aria-selected", i === idx ? "true" : "false"); });
    });
    document.addEventListener("click", function (e) { if (!form.contains(e.target)) close(); });
  }

  /* ---- Dropdowns ---------------------------------------------------- */
  function closeMenus(except) {
    document.querySelectorAll(".dropdown-menu").forEach(function (m) {
      if (m !== except && !m.hidden) { m.hidden = true; var b = m.previousElementSibling; if (b) b.setAttribute("aria-expanded", "false"); }
    });
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-dropdown]");
    if (t) {
      var menuEl = t.parentElement.querySelector(".dropdown-menu");
      closeMenus(menuEl); menuEl.hidden = !menuEl.hidden; t.setAttribute("aria-expanded", menuEl.hidden ? "false" : "true");
      if (!menuEl.hidden) { var f = menuEl.querySelector("a,button"); if (f) f.focus(); }
      return;
    }
    if (!e.target.closest(".dropdown-menu") || e.target.closest(".dropdown-menu a, .dropdown-menu button")) closeMenus();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { closeMenus(); if (app.classList.contains("drawer-open")) setDrawer(false); }
    if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test((e.target.tagName || "")) && !e.target.isContentEditable) {
      var q = document.getElementById("global-q"); if (q) { e.preventDefault(); q.focus(); }
    }
  });

  /* ---- Copy buttons (delegated, work on every page) ----------------- */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy-prompt]");
    if (btn) {
      var text = btn.getAttribute("data-copy-prompt");
      PCH.copy(text, "Prompt copied to the clipboard.").then(function (ok) {
        if (ok && btn.dataset.promptId) PCH.post("/api/prompts/" + btn.dataset.promptId + "/copy").catch(function () { /* counting is best-effort */ });
      });
      return;
    }
    var src = e.target.closest("[data-copy-text-from]");
    if (src) { var el = document.querySelector(src.getAttribute("data-copy-text-from")); if (el) PCH.copy(el.value || el.textContent, "Copied."); }
    var diag = e.target.closest("[data-send-diagnostic]");
    if (diag) { var d = document.getElementById("prompt-data"); if (d) PCH.handoff.set("diagnose", JSON.parse(d.textContent).full_prompt); }
    var closeBtn = e.target.closest("[data-close]");
    if (closeBtn) { var dlg = closeBtn.closest("dialog"); if (dlg) dlg.close(); }
  });

  PCH.showFlash();
})();
