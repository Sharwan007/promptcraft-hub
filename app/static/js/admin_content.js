/* Generic content manager for categories, subcategories, tags, lessons, glossary and examples. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var tabs = document.getElementById("content-tabs"), manager = document.getElementById("manager");
  if (!tabs) return;
  var dlg = document.getElementById("res-dialog"), form = document.getElementById("res-form"), fields = document.getElementById("res-fields");
  var ICONS = ["folder", "briefcase", "clipboard", "refresh", "headset", "database", "table", "presentation", "users", "mail", "bar-chart", "code", "megaphone", "user-plus", "coins", "search", "zap", "book", "layers"];
  var cache = { categories: [] };

  function checksToText(checks) {
    return (checks || []).map(function (c) { return [c.question, c.options.join(" ;; "), String(c.correct_index + 1), c.explanation || ""].join(" | "); }).join("\n");
  }
  function textToChecks(t) {
    return PCH.lines(t).map(function (line) {
      var p = line.split("|").map(function (x) { return x.trim(); });
      if (p.length < 3) throw new Error("Each knowledge check needs: question | option A ;; option B | correct option number | explanation.");
      var opts = p[1].split(";;").map(function (x) { return x.trim(); }).filter(Boolean), idx = parseInt(p[2], 10) - 1;
      if (opts.length < 2 || isNaN(idx) || idx < 0 || idx >= opts.length) throw new Error("A knowledge check needs at least two options and a valid correct option number.");
      return { question: p[0], options: opts, correct_index: idx, explanation: p[3] || "" };
    });
  }

  var RES = {
    categories: { label: "Categories", url: "/api/categories", list: function () { return PCH.get("/api/categories?include_archived=true"); },
      cols: [["Name", function (i) { return i.name; }], ["Prompts", function (i) { return i.prompt_count; }], ["Status", function (i) { return i.archived ? "Archived" : "Active"; }]],
      fields: [{ k: "name", l: "Name", t: "text", req: 1 }, { k: "description", l: "Description", t: "textarea" }, { k: "icon", l: "Icon", t: "select", opts: ICONS }, { k: "sort_order", l: "Sort order", t: "number" }],
      extra: function (i) { return [{ label: i.archived ? "Restore" : "Archive", fn: function () { return PCH.patch("/api/categories/" + i.id + "/archive", { archived: !i.archived }); } }]; } },
    subcategories: { label: "Subcategories", url: "/api/subcategories", list: function () { return PCH.get("/api/subcategories"); },
      cols: [["Name", function (i) { return i.name; }], ["Category", function (i) { var c = cache.categories.filter(function (x) { return x.id === i.category_id; })[0]; return c ? c.name : i.category_id; }]],
      fields: [{ k: "category_id", l: "Category", t: "select", opts: function () { return cache.categories.map(function (c) { return [c.id, c.name]; }); }, num: 1, req: 1 }, { k: "name", l: "Name", t: "text", req: 1 }] },
    tags: { label: "Tags", url: "/api/tags", list: function () { return PCH.get("/api/tags"); },
      cols: [["Tag", function (i) { return "#" + i.name; }], ["Prompts", function (i) { return i.prompt_count; }]], fields: [{ k: "name", l: "Tag name", t: "text", req: 1 }] },
    lessons: { label: "Learning lessons", url: "/api/learning/modules", list: function () { return PCH.get("/api/learning/modules"); },
      cols: [["#", function (i) { return i.number; }], ["Title", function (i) { return i.title; }], ["Status", function (i) { return i.published ? "Published" : "Unpublished"; }]],
      fields: [{ k: "number", l: "Lesson number", t: "number", req: 1 }, { k: "title", l: "Title", t: "text", req: 1 }, { k: "summary", l: "Summary", t: "text" }, { k: "objective", l: "Lesson objective", t: "textarea", req: 1 },
        { k: "explanation", l: "Simple explanation", t: "textarea", req: 1, tall: 1 }, { k: "good_example", l: "Good example", t: "textarea" }, { k: "weak_example", l: "Weak example", t: "textarea" },
        { k: "tips", l: "Practical tips (one per line)", t: "lines" }, { k: "common_mistakes", l: "Common mistakes (one per line)", t: "lines" },
        { k: "checks", l: "Knowledge checks (one per line)", t: "checks", help: "Format: question | option A ;; option B ;; option C | number of the correct option | explanation" },
        { k: "published", l: "Published", t: "check" }],
      extra: function (i) { return [{ label: i.published ? "Unpublish" : "Publish", fn: function () { return PCH.patch("/api/learning/modules/" + i.id + "/flags", { published: !i.published }); } }]; } },
    glossary: { label: "Glossary", url: "/api/glossary", list: function () { return PCH.get("/api/glossary"); },
      cols: [["Term", function (i) { return i.term; }], ["Definition", function (i) { return i.definition.slice(0, 90); }]],
      fields: [{ k: "term", l: "Term", t: "text", req: 1 }, { k: "definition", l: "Definition", t: "textarea", req: 1 }, { k: "example", l: "Example", t: "textarea" }, { k: "published", l: "Published", t: "check" }] },
    examples: { label: "Before & After", url: "/api/examples", list: function () { return PCH.get("/api/examples"); },
      cols: [["#", function (i) { return i.sort_order; }], ["Scenario", function (i) { return i.scenario; }], ["Scores", function (i) { return i.weak_score + " \u2192 " + i.improved_score; }]],
      fields: [{ k: "scenario", l: "Scenario", t: "text", req: 1 }, { k: "description", l: "Description", t: "text" }, { k: "weak_prompt", l: "Weak prompt", t: "textarea", req: 1 },
        { k: "problems", l: "Problems (one per line)", t: "lines" }, { k: "improved_prompt", l: "Improved prompt", t: "textarea", req: 1, tall: 1 }, { k: "improvements", l: "Improvements made (one per line)", t: "lines" },
        { k: "why_better", l: "Why the improved version is better", t: "textarea" }, { k: "expected_difference", l: "Expected difference in output", t: "textarea" },
        { k: "sort_order", l: "Order", t: "number" }, { k: "published", l: "Published", t: "check" }] }
  };
  var current = "categories", editing = null;

  function buildTabs() {
    tabs.innerHTML = "";
    Object.keys(RES).forEach(function (k) {
      var b = PCH.el("button", { type: "button", "class": "tab", role: "tab", text: RES[k].label, "aria-selected": k === current ? "true" : "false" });
      b.addEventListener("click", function () { current = k; buildTabs(); load(); });
      tabs.appendChild(b);
    });
  }

  function load() {
    var r = RES[current];
    manager.innerHTML = '<p><span class="spinner"></span> Loading...</p>';
    PCH.get("/api/categories?include_archived=true").then(function (c) { cache.categories = c; return r.list(); }).then(function (items) {
      manager.innerHTML = "";
      var wrap = PCH.el("div", { "class": "table-wrap" }), t = PCH.el("table", {}), head = PCH.el("tr", {});
      r.cols.forEach(function (c) { head.appendChild(PCH.el("th", { scope: "col", text: c[0] })); });
      head.appendChild(PCH.el("th", { scope: "col", text: "Actions" }));
      t.appendChild(PCH.el("thead", {}, [head]));
      var body = PCH.el("tbody", {});
      if (!items.length) body.innerHTML = '<tr><td colspan="' + (r.cols.length + 1) + '" class="muted">Nothing here yet. Use &ldquo;Add new&rdquo;.</td></tr>';
      items.forEach(function (it) {
        var tr = PCH.el("tr", {});
        r.cols.forEach(function (c) { tr.appendChild(PCH.el("td", { text: String(c[1](it)) })); });
        var act = PCH.el("td", { "class": "nowrap" });
        var mk = function (label, fn, cls) { var b = PCH.el("button", { type: "button", "class": "btn btn-sm " + (cls || "btn-secondary"), text: label, style: "margin-right:.25rem" }); b.addEventListener("click", fn); act.appendChild(b); };
        mk("Edit", function () { open(it); }, "btn-primary");
        (r.extra ? r.extra(it) : []).forEach(function (x) { mk(x.label, function () { x.fn().then(function () { PCH.toast("Updated.", "success"); load(); }, function (e) { PCH.toast(PCH.errorText(e), "error"); }); }); });
        mk("Delete", function () {
          PCH.confirm("Delete this item permanently? This cannot be undone.", { title: "Delete", ok: "Delete" }).then(function (ok) {
            if (ok) PCH.del(r.url + "/" + it.id).then(function () { PCH.toast("Deleted.", "success"); load(); }, function (e) { PCH.toast(PCH.errorText(e), "error"); });
          });
        }, "btn-danger");
        tr.appendChild(act); body.appendChild(tr);
      });
      t.appendChild(body); wrap.appendChild(t); manager.appendChild(wrap);
    }, function (e) { manager.innerHTML = '<div class="alert alert-danger" role="alert">' + PCH.escape(PCH.errorText(e)) + '</div>'; });
  }

  function open(item) {
    editing = item || null; var r = RES[current];
    document.getElementById("res-title").textContent = (item ? "Edit " : "Add ") + r.label.toLowerCase();
    fields.innerHTML = '<div class="alert alert-danger" id="res-errors" role="alert" hidden></div>';
    r.fields.forEach(function (f, n) {
      var id = "rf-" + f.k, wrap = PCH.el("div", { "class": f.t === "check" ? "field check" : "field" }), v = item ? item[f.k] : undefined, input;
      var label = PCH.el("label", { "for": id, text: f.l + (f.req ? " *" : "") });
      if (f.t === "textarea" || f.t === "lines" || f.t === "checks") {
        input = PCH.el("textarea", { "class": "textarea" + (f.tall ? " textarea-lg" : ""), id: id });
        input.value = f.t === "lines" ? (v || []).join("\n") : (f.t === "checks" ? checksToText(v) : (v || ""));
      } else if (f.t === "select") {
        input = PCH.el("select", { "class": "select", id: id });
        var opts = typeof f.opts === "function" ? f.opts() : f.opts.map(function (o) { return [o, o]; });
        opts.forEach(function (o) { var op = document.createElement("option"); op.value = o[0]; op.textContent = o[1]; input.appendChild(op); });
        if (v !== undefined) input.value = String(v);
      } else if (f.t === "check") {
        input = PCH.el("input", { type: "checkbox", id: id }); input.checked = item ? !!v : true;
      } else {
        input = PCH.el("input", { "class": "input", id: id, type: f.t === "number" ? "number" : "text" }); input.value = v === undefined ? (f.t === "number" ? (f.k === "number" ? "" : "0") : "") : v;
      }
      if (f.t === "check") { wrap.appendChild(input); wrap.appendChild(PCH.el("label", { "for": id, text: f.l, style: "margin:0" })); }
      else { wrap.appendChild(label); wrap.appendChild(input); }
      if (f.help) wrap.appendChild(PCH.el("div", { "class": "help", text: f.help }));
      fields.appendChild(wrap);
    });
    dlg.showModal();
  }
  document.getElementById("add-btn").addEventListener("click", function () { open(null); });

  form.addEventListener("submit", function (e) {
    e.preventDefault(); var r = RES[current], body = {}, errs = [], box = document.getElementById("res-errors");
    r.fields.forEach(function (f) {
      var el = document.getElementById("rf-" + f.k), v;
      if (f.t === "check") v = el.checked;
      else if (f.t === "number") v = el.value === "" ? null : Number(el.value);
      else if (f.t === "lines") v = PCH.lines(el.value);
      else if (f.t === "checks") { try { v = textToChecks(el.value); } catch (er) { errs.push(er.message); v = []; } }
      else if (f.t === "select" && f.num) v = Number(el.value);
      else v = el.value.trim();
      if (f.req && (v === "" || v === null || v === undefined)) errs.push(f.l + " is required.");
      body[f.k] = v;
    });
    if (errs.length) { box.innerHTML = "<ul style='margin:0'>" + errs.map(function (x) { return "<li>" + PCH.escape(x) + "</li>"; }).join("") + "</ul>"; box.hidden = false; return; }
    (editing ? PCH.put(r.url + "/" + editing.id, body) : PCH.post(r.url, body)).then(function () { dlg.close(); PCH.toast("Saved.", "success"); load(); },
      function (er) { box.textContent = PCH.errorText(er); box.hidden = false; });
  });

  buildTabs(); load();
})();
