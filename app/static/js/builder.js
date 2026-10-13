/* Prompt Blueprint builder: 9-step wizard, live server-side preview, drafts in localStorage. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var form = document.getElementById("builder-form");
  if (!form) return;
  var catalog = JSON.parse(document.getElementById("catalog-data").textContent);
  var TOTAL = 9, step = 1, lastBuild = null, KEY_DRAFT = "pch-builder-draft", KEY_AUTO = "pch-builder-autosave";

  var DEFAULTS = {
    write: ["a professional business writer", "paragraph"], summarize: ["an analyst who writes accurate summaries", "bullet_list"],
    analyze: ["a senior business analyst", "report"], compare: ["an objective analyst", "table"], plan: ["an experienced project manager", "numbered_steps"],
    brainstorm: ["a creative strategist", "bullet_list"], extract: ["a careful data-extraction specialist", "table"], transform: ["a professional editor", "markdown"],
    code: ["a senior software engineer", "code"], troubleshoot: ["a patient senior developer who debugs systematically", "numbered_steps"],
    presentation: ["a senior presentation strategist", "presentation_outline"], report: ["a business report writer", "report"],
    minutes: ["a professional minute-taker", "meeting_minutes"], user_stories: ["an experienced product owner", "user_story"],
    acceptance_criteria: ["a business analyst and QA lead", "acceptance_criteria"]
  };

  function $(id) { return document.getElementById(id); }
  function checkedValue(name) { var r = form.querySelector('input[name="' + name + '"]:checked'); return r ? r.value : ""; }

  function readState() {
    var c = {};
    form.querySelectorAll("[data-constraint]").forEach(function (el) {
      var k = el.dataset.constraint;
      if (el.type === "checkbox") { if (el.checked) c[k] = el.dataset.check || "yes"; }
      else if (el.value.trim()) c[k] = el.value.trim();
    });
    return { purpose: checkedValue("purpose"), role: $("role").value.trim(), context: $("context").value.trim(), task: $("task").value.trim(),
      inputs: $("inputs").value.trim(), output_format: checkedValue("output_format"), custom_format: $("custom_format").value.trim(),
      constraints: c, quality_criteria: $("quality_criteria").value.trim() };
  }
  function writeState(s) {
    s = s || {};
    ["purpose", "output_format"].forEach(function (n) {
      form.querySelectorAll('input[name="' + n + '"]').forEach(function (r) { r.checked = (r.value === s[n]); });
    });
    $("role").value = s.role || ""; $("context").value = s.context || ""; $("task").value = s.task || "";
    $("inputs").value = s.inputs || ""; $("custom_format").value = s.custom_format || ""; $("quality_criteria").value = s.quality_criteria || "";
    var c = s.constraints || {};
    form.querySelectorAll("[data-constraint]").forEach(function (el) {
      var v = c[el.dataset.constraint];
      if (el.type === "checkbox") el.checked = !!v; else el.value = v || "";
    });
    syncFormat(); syncPurposeHint();
  }
  function isEmpty(s) { return !s.purpose && !s.role && !s.context && !s.task && !s.inputs && !s.output_format && !s.quality_criteria && !Object.keys(s.constraints).length; }

  /* ---- validation ---- */
  function validate(n, s) {
    var msg = "";
    if (n === 1 && !s.purpose) msg = "Choose a purpose to continue.";
    if (n === 2 && s.role.length < 3) msg = "Define a role, for example: a senior business analyst.";
    if (n === 4 && s.task.length < 10) msg = "Describe the task in at least 10 characters. Start with an action verb.";
    if (n === 6 && !s.output_format) msg = "Select an output format.";
    if (n === 6 && s.output_format === "custom" && !s.custom_format) msg = "Describe your custom format.";
    var err = form.querySelector('[data-error="' + n + '"]');
    if (err) { err.textContent = msg; err.hidden = !msg; }
    var field = n === 2 ? $("role") : (n === 4 ? $("task") : null);
    if (field) PCH.fieldError(field, null, msg);
    return !msg;
  }

  /* ---- wizard ---- */
  function show(n) {
    step = Math.max(1, Math.min(TOTAL, n));
    form.querySelectorAll(".step").forEach(function (el) { el.hidden = Number(el.dataset.step) !== step; });
    var s = readState();
    document.querySelectorAll("#stepper button").forEach(function (b) {
      var k = Number(b.dataset.step);
      b.classList.toggle("is-current", k === step); b.classList.toggle("is-done", k < step);
      if (k === step) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    });
    $("btn-back").disabled = step === 1;
    $("btn-next").hidden = step === TOTAL;
    var cur = form.querySelector('.step[data-step="' + step + '"] h3'); if (cur) { cur.setAttribute("tabindex", "-1"); cur.focus({ preventScroll: true }); }
    if (step === TOTAL) renderReview();
    var active = document.querySelector("#stepper .is-current"); if (active && active.scrollIntoView) active.scrollIntoView({ block: "nearest", inline: "center" });
  }
  function goTo(target) {
    var s = readState();
    if (target > step) { for (var n = step; n < target; n++) { if (!validate(n, s)) { show(n); return; } } }
    show(target);
  }
  $("btn-next").addEventListener("click", function () { goTo(step + 1); });
  $("btn-back").addEventListener("click", function () { show(step - 1); });
  document.querySelectorAll("#stepper button").forEach(function (b) { b.addEventListener("click", function () { goTo(Number(b.dataset.step)); }); });
  form.addEventListener("submit", function (e) { e.preventDefault(); });

  /* ---- purpose / format helpers ---- */
  function syncFormat() { $("custom-format-wrap").hidden = checkedValue("output_format") !== "custom"; }
  function syncPurposeHint() {
    var k = checkedValue("purpose"), p = catalog.purposes.filter(function (x) { return x.key === k; })[0];
    $("task-starter").textContent = p ? "Starter idea: \u201C" + p.starter + " ...\u201D" : "";
  }
  form.addEventListener("change", function (e) {
    if (e.target.name === "purpose") {
      syncPurposeHint();
      var d = DEFAULTS[e.target.value];
      if (d) {
        if (!$("role").value.trim()) $("role").value = d[0];
        if (!checkedValue("output_format")) { var r = $("of-" + d[1]); if (r) { r.checked = true; syncFormat(); } }
      }
    }
    if (e.target.name === "output_format") syncFormat();
  });
  $("role-select").addEventListener("change", function () { if (this.value) { $("role").value = this.value; update(); } });
  document.querySelectorAll("[data-add-quality]").forEach(function (b) {
    b.addEventListener("click", function () {
      var ta = $("quality_criteria"), line = b.dataset.addQuality;
      if (ta.value.split("\n").map(function (x) { return x.trim(); }).indexOf(line) === -1) ta.value = (ta.value.trim() ? ta.value.trim() + "\n" : "") + line;
      update();
    });
  });

  /* ---- live preview ---- */
  var seq = 0;
  function update() {
    var s = readState(), my = ++seq;
    autosave(s);
    PCH.post("/api/prompts/build", s).then(function (r) {
      if (my !== seq) return;
      lastBuild = r;
      $("preview").textContent = r.prompt || "Your prompt appears here as you fill in the Blueprint.";
      var bar = $("completion-bar"); bar.setAttribute("aria-valuenow", r.completion_score); bar.firstElementChild.style.width = r.completion_score + "%";
      $("completion-text").textContent = r.completion_score + "%";
      $("quality-text").textContent = r.quality ? r.quality.score + " / 100 (" + r.quality.label + ")" : "-";
      var ul = $("missing-list"); ul.innerHTML = "";
      if (!r.missing.length) { var li = PCH.el("li", {}); li.innerHTML = '<svg class="icon" aria-hidden="true"><use href="/static/icons/sprite.svg#i-check-circle"></use></svg>'; li.appendChild(PCH.el("span", { text: "All Blueprint sections are filled in." })); ul.appendChild(li); }
      r.missing.forEach(function (m) {
        var li = PCH.el("li", {}); li.innerHTML = '<svg class="icon" aria-hidden="true"><use href="/static/icons/sprite.svg#i-alert"></use></svg>';
        li.appendChild(PCH.el("span", { text: m.guidance })); ul.appendChild(li);
      });
      if (step === TOTAL) renderReview();
    }, function (e) { if (my === seq) PCH.toast(PCH.errorText(e), "error"); });
  }
  var updateSoon = PCH.debounce(update, 250);
  form.addEventListener("input", updateSoon); form.addEventListener("change", updateSoon);

  function renderReview() {
    var box = $("review-missing"); box.innerHTML = "";
    if (!lastBuild) return;
    var div = PCH.el("div", { "class": "alert " + (lastBuild.valid && !lastBuild.missing.length ? "alert-success" : "alert-warning"), role: "status" });
    var text;
    if (!lastBuild.valid) text = "A few required items are missing. Use the Back button or the step list to complete them.";
    else if (lastBuild.missing.length) text = "Your prompt is usable. " + lastBuild.missing.length + " optional section(s) could still be improved: " + lastBuild.missing.map(function (m) { return m.section.replace("_", " "); }).join(", ") + ".";
    else text = "Every section is filled in. Copy, save or export your prompt from the preview panel.";
    div.appendChild(PCH.el("div", { text: text }));
    box.appendChild(div);
    Object.keys(lastBuild.step_errors || {}).forEach(function (k) { box.appendChild(PCH.el("p", { "class": "error-text", text: "Step " + k + ": " + lastBuild.step_errors[k].join(" ") })); });
  }

  /* ---- drafts ---- */
  function stamp() { var d = new Date(); return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2); }
  function autosave(s) {
    try { if (isEmpty(s)) localStorage.removeItem(KEY_AUTO); else localStorage.setItem(KEY_AUTO, JSON.stringify({ state: s, step: step, at: Date.now() })); } catch (e) { /* storage unavailable */ }
  }
  $("btn-save-draft").addEventListener("click", function () {
    var s = readState();
    try { localStorage.setItem(KEY_DRAFT, JSON.stringify({ state: s, step: step, at: Date.now() })); $("draft-state").textContent = "Draft saved " + stamp(); PCH.toast("Draft saved in this browser.", "success"); }
    catch (e) { PCH.toast("The browser blocked saving the draft. Copy your prompt instead.", "error"); }
  });
  function loadDraft(key) {
    try { var d = JSON.parse(localStorage.getItem(key) || "null"); if (d && d.state) { writeState(d.state); show(d.step || 1); update(); return true; } } catch (e) { /* ignore */ }
    return false;
  }
  $("resume-draft").addEventListener("click", function () {
    if (loadDraft(KEY_DRAFT) || loadDraft(KEY_AUTO)) PCH.toast("Draft restored.", "success"); else PCH.toast("There is no saved draft yet. Use Save draft first.", "info");
  });
  $("reset-builder").addEventListener("click", function () {
    PCH.confirm("Clear everything in the builder and start again? A draft you saved with Save draft is kept.", { title: "Reset builder", ok: "Reset" }).then(function (ok) {
      if (!ok) return; writeState({}); try { localStorage.removeItem(KEY_AUTO); } catch (e) { /* ignore */ } show(1); update(); PCH.toast("Builder reset.", "info");
    });
  });
  $("load-sample").addEventListener("click", function () {
    var go = function () { writeState(catalog.sample); show(9); update(); PCH.toast("Sample loaded. Edit any step to make it your own.", "success"); };
    if (isEmpty(readState())) go(); else PCH.confirm("Replace what you have entered with the sample?", { title: "Load sample", ok: "Load sample", danger: false }).then(function (ok) { if (ok) go(); });
  });

  /* ---- actions ---- */
  function currentPrompt() { return (lastBuild && lastBuild.prompt) || ""; }
  function titleFromTask() { var t = readState().task || "Built prompt"; return t.replace(/\s+/g, " ").slice(0, 60); }
  $("btn-copy").addEventListener("click", function () { var p = currentPrompt(); if (!p) { PCH.toast("Nothing to copy yet. Fill in a few steps first.", "info"); return; } PCH.copy(p, "Prompt copied to the clipboard."); });
  $("btn-save").addEventListener("click", function () {
    var p = currentPrompt(); if (!p) { PCH.toast("Nothing to save yet. Fill in a few steps first.", "info"); return; }
    PCH.ask("Name for this prompt", titleFromTask(), { title: "Save to My Prompts" }).then(function (title) {
      if (!title) return;
      PCH.post("/api/custom-prompts", { title: title, description: "Built with the Prompt Builder.", content: p, origin: "builder", tags: ["builder"] })
        .then(function () { PCH.toast("Saved to My Prompts.", "success"); }, function (e) { PCH.toast(PCH.errorText(e), "error"); });
    });
  });
  document.querySelectorAll("[data-export]").forEach(function (b) {
    b.addEventListener("click", function () { var p = currentPrompt(); if (!p) { PCH.toast("Nothing to export yet.", "info"); return; } PCH.exportPrompt(titleFromTask(), p, b.dataset.export); });
  });

  /* ---- start-up: hand-off from Before & After, else restore unsaved work ---- */
  var handoff = PCH.handoff.take("builder");
  if (handoff) {
    var s = { purpose: "", role: handoff.role || "", context: handoff.context || "", task: handoff.task || "", inputs: handoff.inputs || "",
      output_format: handoff.output_text ? "custom" : "", custom_format: handoff.output_text || "", constraints: {}, quality_criteria: handoff.quality_criteria || "" };
    if (handoff.audience) s.constraints.audience = handoff.audience;
    if (handoff.tone) s.constraints.tone = handoff.tone;
    if (handoff.constraints_text) s.constraints.extra = handoff.constraints_text;
    writeState(s); show(1); update(); PCH.toast("Loaded into the builder. Choose a purpose to continue.", "info");
  } else if (!loadDraft(KEY_AUTO)) { show(1); update(); } else { PCH.toast("Restored your unsaved work. Use Reset to start fresh.", "info"); }
})();
