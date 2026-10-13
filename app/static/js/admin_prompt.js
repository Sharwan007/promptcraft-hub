/* Admin prompt form: create / edit a library prompt. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var form = document.getElementById("prompt-form");
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var existing = JSON.parse($("prompt-json").textContent || "{}");
  var editing = existing && existing.id ? existing : null;

  function tools() { return Array.prototype.map.call(form.querySelectorAll('input[name="tools"]:checked'), function (c) { return c.value; }); }
  function subs() {
    var opt = $("f-cat").selectedOptions[0], dl = $("sub-list"); dl.innerHTML = "";
    if (opt && opt.dataset.subs) opt.dataset.subs.split("|").filter(Boolean).forEach(function (s) { var o = document.createElement("option"); o.value = s; dl.appendChild(o); });
  }
  $("f-cat").addEventListener("change", subs);

  function fill(p) {
    $("f-title").value = p.title || ""; $("f-slug").value = p.slug || ""; $("f-desc").value = p.description || "";
    $("f-cat").value = p.category || ""; subs(); $("f-sub").value = p.subcategory || ""; $("f-diff").value = p.difficulty || "Beginner";
    $("f-role").value = p.user_role || ""; $("f-use").value = p.use_case || ""; $("f-tags").value = (p.tags || []).join(", ");
    form.querySelectorAll('input[name="tools"]').forEach(function (c) { c.checked = (p.ai_tools || []).indexOf(c.value) !== -1; });
    $("f-published").checked = p.published !== false; $("f-featured").checked = !!p.featured;
    var c = p.components || {};
    $("c-role").value = String(c.role || "").replace(/^Act as /i, "").replace(/\.$/, ""); $("c-context").value = c.context || ""; $("c-task").value = c.task || "";
    $("c-input").value = c.input || ""; $("c-output").value = c.output_format || "";
    $("f-constraints").value = (p.constraints || []).join("\n"); $("c-quality").value = [].concat(c.quality_criteria || []).join("\n");
    $("f-full").value = p.full_prompt || ""; $("f-why").value = p.why_it_works || ""; $("f-expected").value = p.expected_output || "";
    $("f-exout").value = p.example_output || ""; $("f-tips").value = (p.customization_tips || []).join("\n"); $("f-mistakes").value = (p.common_mistakes || []).join("\n");
    $("f-exin").value = Object.keys(p.example_inputs || {}).map(function (k) { return k + " = " + p.example_inputs[k]; }).join("\n");
  }
  if (editing) fill(editing); else subs();

  function composed() {
    var parts = [], role = $("c-role").value.trim();
    if (role) parts.push(/^(act as|you are)/i.test(role) ? role.replace(/\.?$/, ".") : "Act as " + role.replace(/\.$/, "") + ".");
    var add = function (label, v) { if (v) parts.push(label + ":\n" + v); };
    add("Context", $("c-context").value.trim()); add("Task", $("c-task").value.trim()); add("Input", $("c-input").value.trim()); add("Output format", $("c-output").value.trim());
    var con = PCH.lines($("f-constraints").value), q = PCH.lines($("c-quality").value);
    if (con.length) parts.push("Constraints:\n" + con.map(function (x) { return "- " + x; }).join("\n"));
    if (q.length) parts.push("Quality criteria:\n" + q.map(function (x) { return "- " + x; }).join("\n"));
    return parts.join("\n\n");
  }
  $("compose-btn").addEventListener("click", function () {
    var t = composed(); if (!t) { PCH.toast("Fill in at least one Blueprint field first.", "info"); return; }
    if ($("f-full").value.trim()) { PCH.confirm("Replace the current full prompt with one composed from the Blueprint fields?", { title: "Compose full prompt", ok: "Replace", danger: false }).then(function (ok) { if (ok) $("f-full").value = t; }); }
    else $("f-full").value = t;
  });
  $("score-btn").addEventListener("click", function () {
    var text = $("f-full").value.trim() || composed(); if (!text) { PCH.toast("There is no prompt text to score yet.", "info"); return; }
    PCH.post("/api/prompts/analyze", { prompt: text }).then(function (r) { $("score-out").textContent = "Quality score: " + r.score + " / 100 (" + r.label + ")"; }, function (e) { PCH.toast(PCH.errorText(e), "error"); });
  });

  function payload() {
    var full = $("f-full").value.trim() || composed();
    var role = $("c-role").value.trim(), exin = {};
    PCH.lines($("f-exin").value).forEach(function (l) { var i = l.indexOf("="); if (i > 0) exin[l.slice(0, i).trim()] = l.slice(i + 1).trim(); });
    return {
      title: $("f-title").value.trim(), slug: $("f-slug").value.trim() || null, description: $("f-desc").value.trim(), full_prompt: full,
      category: $("f-cat").value || null, subcategory: $("f-sub").value.trim() || null, user_role: $("f-role").value.trim(), use_case: $("f-use").value.trim(),
      ai_tools: tools().length ? tools() : ["Tool-independent"], difficulty: $("f-diff").value, tags: PCH.comma($("f-tags").value),
      expected_output: $("f-expected").value.trim(), required_inputs: [], example_inputs: exin, example_output: $("f-exout").value.trim(),
      why_it_works: $("f-why").value.trim(), customization_tips: PCH.lines($("f-tips").value), common_mistakes: PCH.lines($("f-mistakes").value),
      constraints: PCH.lines($("f-constraints").value),
      components: { role: role ? (/^(act as|you are)/i.test(role) ? role : "Act as " + role + ".") : "", context: $("c-context").value.trim(), task: $("c-task").value.trim(),
        input: $("c-input").value.trim(), output_format: $("c-output").value.trim(), constraints: PCH.lines($("f-constraints").value), quality_criteria: PCH.lines($("c-quality").value) },
      featured: $("f-featured").checked, published: $("f-published").checked
    };
  }
  function showErrors(list) {
    var box = $("form-errors"), ul = $("form-error-list"); ul.innerHTML = "";
    list.forEach(function (m) { ul.appendChild(PCH.el("li", { text: m })); }); box.hidden = !list.length;
    if (list.length) box.scrollIntoView({ behavior: "smooth", block: "center" });
  }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var p = payload(), errs = [];
    if (p.title.length < 3) errs.push("Title must be at least 3 characters.");
    if (p.description.length < 5) errs.push("Short description must be at least 5 characters.");
    if (!p.category) errs.push("Choose a category.");
    if (p.full_prompt.length < 10) errs.push("Enter the full prompt or fill in the Blueprint fields (at least 10 characters).");
    showErrors(errs); if (errs.length) return;
    var btn = $("save-btn"); PCH.busy(btn, true, "Saving...");
    (editing ? PCH.put("/api/prompts/" + editing.id, p) : PCH.post("/api/prompts", p)).then(function () {
      PCH.flash(editing ? "Prompt saved." : "Prompt created."); window.location.href = "/admin";
    }, function (er) { showErrors([PCH.errorText(er)]); PCH.busy(btn, false); });
  });
})();
