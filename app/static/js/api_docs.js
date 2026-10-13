/* Offline API reference built from /openapi.json (no external assets). */
(function () {
  "use strict";
  var PCH = window.PCH, list = document.getElementById("api-list"), filter = document.getElementById("api-filter");
  if (!list) return;
  var spec = null;

  function resolve(ref) { var parts = ref.replace("#/", "").split("/"), o = spec; parts.forEach(function (p) { o = o && o[p]; }); return o; }
  function sample(schema, depth) {
    depth = depth || 0; if (!schema || depth > 3) return null;
    if (schema.$ref) return sample(resolve(schema.$ref), depth + 1);
    if (schema.anyOf) return sample(schema.anyOf.filter(function (s) { return s.type !== "null"; })[0], depth + 1);
    if (schema.default !== undefined) return schema.default;
    if (schema.type === "object" || schema.properties) { var o = {}; Object.keys(schema.properties || {}).forEach(function (k) { o[k] = sample(schema.properties[k], depth + 1); }); return o; }
    if (schema.type === "array") return [];
    if (schema.type === "integer" || schema.type === "number") return 0;
    if (schema.type === "boolean") return false;
    return "";
  }

  function render() {
    var q = (filter.value || "").trim().toLowerCase(), groups = {};
    Object.keys(spec.paths).forEach(function (path) {
      Object.keys(spec.paths[path]).forEach(function (method) {
        var op = spec.paths[path][method], tag = (op.tags || ["Other"])[0];
        if (q && (path + " " + method + " " + (op.summary || "") + " " + tag).toLowerCase().indexOf(q) === -1) return;
        (groups[tag] = groups[tag] || []).push({ path: path, method: method, op: op });
      });
    });
    list.innerHTML = "";
    Object.keys(groups).sort().forEach(function (tag) {
      list.appendChild(PCH.el("h2", { text: tag, style: "margin-top:1.25rem" }));
      groups[tag].forEach(function (e) { list.appendChild(opEl(e)); });
    });
    if (!list.children.length) list.innerHTML = '<div class="empty"><h3>No endpoints match</h3></div>';
  }

  function opEl(e) {
    var d = PCH.el("details", { "class": "op" }), s = PCH.el("summary", {});
    s.appendChild(PCH.el("span", { "class": "m m-" + e.method, text: e.method.toUpperCase() }));
    s.appendChild(PCH.el("code", { text: e.path })); s.appendChild(PCH.el("span", { "class": "muted", text: e.op.summary || "" }));
    d.appendChild(s);
    var body = PCH.el("div", { "class": "body" });
    var params = (e.op.parameters || []);
    if (params.length) {
      body.appendChild(PCH.el("h4", { text: "Parameters" }));
      var ul = PCH.el("ul", {}); params.forEach(function (p) { ul.appendChild(PCH.el("li", { text: p["in"] + " " + p.name + (p.required ? " (required)" : "") + (p.schema && p.schema.type ? " : " + p.schema.type : "") })); }); body.appendChild(ul);
    }
    var inputs = {}, ta = null;
    params.forEach(function (p) {
      var row = PCH.el("div", { "class": "field", style: "max-width:420px" });
      row.appendChild(PCH.el("label", { text: p.name + " (" + p["in"] + ")" })); var inp = PCH.el("input", { "class": "input", maxlength: "200" }); row.appendChild(inp); inputs[p.name] = { el: inp, where: p["in"] }; body.appendChild(row);
    });
    var rb = e.op.requestBody && e.op.requestBody.content && e.op.requestBody.content["application/json"];
    if (rb) {
      body.appendChild(PCH.el("h4", { text: "JSON body" }));
      ta = PCH.el("textarea", { "class": "textarea mono", "aria-label": "JSON request body" }); ta.value = JSON.stringify(sample(rb.schema), null, 2); body.appendChild(ta);
    } else if (e.op.requestBody) body.appendChild(PCH.el("p", { "class": "muted", text: "This endpoint takes a file upload; use the Administration screens." }));
    var out = PCH.el("pre", { "class": "prompt-box", style: "margin-top:.6rem", hidden: "" });
    if (!e.op.requestBody || rb) {
      var btn = PCH.el("button", { type: "button", "class": "btn btn-primary btn-sm", text: "Try it" });
      btn.addEventListener("click", function () {
        var url = e.path, qs = new URLSearchParams();
        Object.keys(inputs).forEach(function (n) { var v = inputs[n].el.value.trim(); if (!v) return; if (inputs[n].where === "path") url = url.replace("{" + n + "}", encodeURIComponent(v)); else qs.set(n, v); });
        if (/\{/.test(url)) { out.hidden = false; out.textContent = "Fill in every path parameter first."; return; }
        var init = { method: e.method.toUpperCase(), headers: { "Accept": "application/json", "X-CSRF-Token": PCH.csrf() }, credentials: "same-origin" };
        if (ta) { init.headers["Content-Type"] = "application/json"; init.body = ta.value; }
        fetch(url + (qs.toString() ? "?" + qs.toString() : ""), init).then(function (r) { return r.text().then(function (t) { out.hidden = false; try { t = JSON.stringify(JSON.parse(t), null, 2); } catch (x) { /* plain text */ } out.textContent = r.status + " " + r.statusText + "\n\n" + t.slice(0, 6000); }); },
          function () { out.hidden = false; out.textContent = "The request could not be sent."; });
      });
      body.appendChild(btn);
    }
    body.appendChild(out); d.appendChild(body); return d;
  }

  PCH.get("/openapi.json").then(function (s) { spec = s; render(); filter.addEventListener("input", PCH.debounce(render, 150)); },
    function (e) { list.innerHTML = '<div class="alert alert-danger" role="alert">' + PCH.escape(PCH.errorText(e)) + '</div>'; });
})();
