/* Shared helpers: API calls with CSRF, toasts, dialogs, clipboard, downloads, hand-offs. No dependencies. */
(function () {
  "use strict";
  var PCH = window.PCH = window.PCH || {};

  PCH.csrf = function () {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  };

  PCH.escape = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  PCH.debounce = function (fn, ms) {
    var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms || 250); };
  };

  PCH.el = function (tag, attrs, children) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") e.textContent = attrs[k];
      else if (k === "class") e.className = attrs[k];
      else if (k.slice(0, 2) === "on" && typeof attrs[k] === "function") e.addEventListener(k.slice(2), attrs[k]);
      else e.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  };

  /* ---- API ---------------------------------------------------------- */
  PCH.ApiError = function (status, body) {
    var err = (body && body.error) || {};
    this.status = status;
    this.message = err.message || "Something went wrong. Please try again.";
    this.details = err.details || [];
    this.hint = err.hint || "";
  };
  PCH.ApiError.prototype = Object.create(Error.prototype);

  PCH.api = function (method, url, body, opts) {
    opts = opts || {};
    var headers = { "Accept": "application/json", "X-CSRF-Token": PCH.csrf() };
    var init = { method: method, headers: headers, credentials: "same-origin" };
    if (body instanceof FormData) { init.body = body; }
    else if (body !== undefined && body !== null) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    return fetch(url, init).then(function (res) {
      if (opts.raw) { if (!res.ok) return res.json().catch(function () { return {}; }).then(function (b) { throw new PCH.ApiError(res.status, b); }); return res; }
      return res.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { data = null; }
        if (!res.ok) throw new PCH.ApiError(res.status, data);
        return data;
      });
    }, function () {
      throw new PCH.ApiError(0, { error: { message: "Could not reach the application. Check that PromptCraft Hub is still running, then try again." } });
    });
  };
  PCH.get = function (u) { return PCH.api("GET", u); };
  PCH.post = function (u, b) { return PCH.api("POST", u, b === undefined ? null : b); };
  PCH.put = function (u, b) { return PCH.api("PUT", u, b); };
  PCH.patch = function (u, b) { return PCH.api("PATCH", u, b); };
  PCH.del = function (u) { return PCH.api("DELETE", u); };

  PCH.errorText = function (e) {
    if (!(e instanceof PCH.ApiError)) return "Unexpected error. Please try again.";
    var t = e.message;
    if (e.details && e.details.length) t += " " + e.details.join("; ");
    return t;
  };

  /* ---- Toasts ------------------------------------------------------- */
  PCH.toast = function (message, kind, ms) {
    var stack = document.getElementById("toast-stack");
    if (!stack) return;
    kind = kind || "info";
    var icon = kind === "success" ? "check-circle" : (kind === "error" ? "alert" : "info");
    var t = PCH.el("div", { "class": "toast toast-" + kind });
    t.innerHTML = '<svg class="icon" aria-hidden="true"><use href="/static/icons/sprite.svg#i-' + icon + '"></use></svg>';
    t.appendChild(PCH.el("div", { text: message }));
    var close = PCH.el("button", { "class": "btn-icon", type: "button", "aria-label": "Dismiss notification" });
    close.innerHTML = '<svg class="icon" aria-hidden="true"><use href="/static/icons/sprite.svg#i-x"></use></svg>';
    close.addEventListener("click", function () { t.remove(); });
    t.appendChild(close);
    stack.appendChild(t);
    setTimeout(function () { t.remove(); }, ms || (kind === "error" ? 8000 : 4000));
  };
  PCH.flash = function (message, kind) { try { sessionStorage.setItem("pch-flash", JSON.stringify({ m: message, k: kind || "success" })); } catch (e) { /* ignore */ } };
  PCH.showFlash = function () {
    try { var f = sessionStorage.getItem("pch-flash"); if (f) { sessionStorage.removeItem("pch-flash"); f = JSON.parse(f); PCH.toast(f.m, f.k); } } catch (e) { /* ignore */ }
  };

  /* ---- Dialogs ------------------------------------------------------ */
  PCH.confirm = function (message, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var d = document.getElementById("confirm-dialog");
      if (!d || !d.showModal) { resolve(window.confirm(message)); return; }
      d.querySelector("#confirm-title").textContent = opts.title || "Please confirm";
      d.querySelector("#confirm-message").textContent = message;
      var ok = d.querySelector("#confirm-ok");
      ok.textContent = opts.ok || "Confirm";
      ok.className = "btn " + (opts.danger === false ? "btn-primary" : "btn-danger");
      d.returnValue = "";
      var done = function () { d.removeEventListener("close", done); resolve(d.returnValue === "ok"); };
      d.addEventListener("close", done);
      d.showModal();
    });
  };

  PCH.ask = function (label, initial, opts) {
    opts = opts || {};
    return new Promise(function (resolve) {
      var d = document.getElementById("ask-dialog");
      if (!d || !d.showModal) { resolve(window.prompt(label, initial || "")); return; }
      var input = d.querySelector("#ask-input"), err = d.querySelector("#ask-error");
      d.querySelector("#ask-title").textContent = opts.title || "Enter a value";
      d.querySelector("#ask-label").textContent = label;
      d.querySelector("#ask-ok").textContent = opts.ok || "Save";
      input.value = initial || ""; err.hidden = true; d.returnValue = "";
      var form = d.querySelector("#ask-form");
      var guard = function (ev) {
        if (ev.submitter && ev.submitter.value === "ok" && !input.value.trim()) {
          ev.preventDefault(); err.textContent = "Please enter a value."; err.hidden = false; input.focus();
        }
      };
      var onClose = function () {
        if (d.returnValue === "ok") { resolve(input.value.trim()); } else { resolve(null); }
        d.removeEventListener("close", onClose);
        form.removeEventListener("submit", guard);
      };
      form.addEventListener("submit", guard);
      d.addEventListener("close", onClose);
      d.showModal(); input.focus();
    });
  };

  /* ---- Clipboard / download ---------------------------------------- */
  PCH.copyText = function (text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy") ? resolve() : reject(new Error("copy failed")); } catch (e) { reject(e); }
      document.body.removeChild(ta);
    });
  };
  PCH.copy = function (text, okMessage) {
    return PCH.copyText(text).then(function () { PCH.toast(okMessage || "Copied to the clipboard.", "success"); return true; },
      function () { PCH.toast("Copy was blocked by the browser. Select the text and press Ctrl+C.", "error"); return false; });
  };

  PCH.safeName = function (s, ext) {
    var base = String(s || "prompt").normalize("NFKD").replace(/[^\w\- ]+/g, "").trim().replace(/\s+/g, "-").toLowerCase().slice(0, 60) || "prompt";
    return base + (ext ? "." + ext : "");
  };
  PCH.download = function (filename, content, mime) {
    var blob = new Blob([content], { type: (mime || "text/plain") + ";charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = filename; document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 500);
  };
  /* Server-rendered export (safe file name, consistent formats). */
  PCH.exportPrompt = function (title, content, fmt) {
    return PCH.api("POST", "/api/prompts/render", { title: title || "prompt", content: content, format: fmt }, { raw: true })
      .then(function (res) { return res.blob().then(function (b) {
        var cd = res.headers.get("Content-Disposition") || "", m = /filename="([^"]+)"/.exec(cd);
        var url = URL.createObjectURL(b), a = document.createElement("a");
        a.href = url; a.download = m ? m[1] : PCH.safeName(title, fmt); document.body.appendChild(a); a.click();
        setTimeout(function () { URL.revokeObjectURL(url); a.remove(); }, 500);
      }); })
      .catch(function (e) { PCH.toast(PCH.errorText(e), "error"); });
  };

  /* ---- Hand-off between tools (sessionStorage) ---------------------- */
  PCH.handoff = {
    set: function (key, value) { try { sessionStorage.setItem("pch-handoff-" + key, JSON.stringify(value)); } catch (e) { /* ignore */ } },
    take: function (key) {
      try { var v = sessionStorage.getItem("pch-handoff-" + key); if (v !== null) { sessionStorage.removeItem("pch-handoff-" + key); return JSON.parse(v); } } catch (e) { /* ignore */ }
      return null;
    }
  };

  PCH.busy = function (btn, on, label) {
    if (!btn) return;
    if (on) { btn.dataset.label = btn.innerHTML; btn.disabled = true; btn.innerHTML = '<span class="spinner" aria-hidden="true"></span> ' + (label || "Working..."); }
    else { btn.disabled = false; if (btn.dataset.label) btn.innerHTML = btn.dataset.label; }
  };

  PCH.scoreRing = function (score, size, label) {
    var cls = score < 40 ? "ring-low" : (score < 60 ? "ring-mid" : (score < 80 ? "ring-good" : "ring-high"));
    return '<div class="score-ring ' + cls + ' ' + (size || "") + '" style="--pct:' + Number(score) + '" role="img" aria-label="Score ' + Number(score) +
      ' out of 100' + (label ? ', ' + PCH.escape(label) : '') + '"><div><strong>' + Number(score) + '</strong><span>/ 100</span></div></div>';
  };

  PCH.statusBadge = function (status) {
    var labels = { present: "Present", partial: "Partially present", missing: "Missing", needs_clarification: "Needs clarification" };
    var icons = { present: "check-circle", partial: "info", missing: "x-circle", needs_clarification: "alert" };
    return '<span class="badge badge-' + status + '"><svg class="icon" aria-hidden="true"><use href="/static/icons/sprite.svg#i-' + (icons[status] || "info") + '"></use></svg> ' + (labels[status] || status) + '</span>';
  };

  PCH.breakdownHtml = function (rows) {
    return rows.map(function (b) {
      var pct = b.max ? Math.round(100 * b.points / b.max) : 0;
      return '<div class="bar-row"><span>' + PCH.escape(b.label) + '</span><div class="progress" aria-hidden="true"><span style="width:' + pct + '%"></span></div><span class="pts">' + b.points + ' / ' + b.max + '</span></div>';
    }).join("");
  };

  PCH.fieldError = function (input, errEl, message) {
    if (message) { if (input) { input.classList.add("is-invalid"); input.setAttribute("aria-invalid", "true"); } if (errEl) { errEl.textContent = message; errEl.hidden = false; } }
    else { if (input) { input.classList.remove("is-invalid"); input.removeAttribute("aria-invalid"); } if (errEl) { errEl.hidden = true; errEl.textContent = ""; } }
  };

  PCH.lines = function (s) { return String(s || "").split(/\r?\n/).map(function (x) { return x.replace(/^[-*\u2022\s]+/, "").trim(); }).filter(Boolean); };
  PCH.comma = function (s) { return String(s || "").split(",").map(function (x) { return x.trim(); }).filter(Boolean); };

  PCH.reload = function (msg, kind) { if (msg) PCH.flash(msg, kind); window.location.reload(); };
})();
