/* Prompt Diagnostic: component statuses, risks, score breakdown, recommendations, downloads. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var form = document.getElementById("diag-form");
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var area = $("prompt"), result = $("result"), last = null, lastText = "";
  var SAMPLE = "Create a presentation.";

  function render(r) {
    last = r; result.hidden = false;
    $("ring").innerHTML = PCH.scoreRing(r.score, "", r.label);
    $("label").textContent = r.label;
    $("score-note").textContent = "Rule-based score out of 100 (not AI). Detected type: " + r.use_case_label + ".";
    $("adjustments").innerHTML = (r.adjustments || []).map(function (a) { return '<p class="small" style="margin:.3rem 0"><span class="badge badge-missing">' + a.points + '</span> ' + PCH.escape(a.label) + ': ' + PCH.escape(a.reason) + '</p>'; }).join("");
    $("breakdown").innerHTML = PCH.breakdownHtml(r.breakdown);
    $("components").innerHTML = r.components.map(function (c) {
      return '<div class="diag-row"><strong>' + PCH.escape(c.label) + '</strong><div>' + PCH.statusBadge(c.status) + '</div><div>' +
        (c.evidence ? '<div class="evidence">Found: ' + PCH.escape(c.evidence) + '</div>' : '') +
        (c.clarification ? '<div>' + PCH.escape(c.clarification) + '</div>' : '') +
        (c.recommendation ? '<div>' + PCH.escape(c.recommendation) + '</div>' : '<div class="muted">No action needed.</div>') + '</div></div>';
    }).join("");
    $("risks").innerHTML = (r.risk_checks || []).map(function (c) {
      var ok = c.status === "present";
      return '<div class="diag-row"><strong>' + PCH.escape(c.label) + '</strong><div>' + (ok ? '<span class="badge badge-present"><svg class="icon" aria-hidden="true"><use href="/static/icons/sprite.svg#i-check-circle"></use></svg> None detected</span>' : PCH.statusBadge("needs_clarification")) + '</div><div>' + PCH.escape(c.summary) + '</div></div>';
    }).join("");
    fill($("strengths"), r.strengths, "No strengths detected yet. Start with a clear task.");
    fill($("recs"), r.recommendations, "No recommendations. This prompt covers every component.");
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function fill(el, items, empty) {
    el.innerHTML = "";
    if (!items || !items.length) { el.appendChild(PCH.el("li", { "class": "muted", text: empty })); return; }
    items.forEach(function (t) { el.appendChild(PCH.el("li", { text: t })); });
  }

  function run(text) {
    var err = $("prompt-error");
    if (!text.trim()) { PCH.fieldError(area, err, "Paste a prompt to diagnose."); area.focus(); return; }
    PCH.fieldError(area, err, "");
    lastText = text;
    var btn = $("diag-btn"); PCH.busy(btn, true, "Diagnosing...");
    PCH.post("/api/prompts/diagnose", { prompt: text, use_case: $("use-case").value || null })
      .then(render, function (e) { PCH.fieldError(area, err, PCH.errorText(e)); PCH.toast(PCH.errorText(e), "error"); })
      .then(function () { PCH.busy(btn, false); });
  }
  form.addEventListener("submit", function (e) { e.preventDefault(); run(area.value); });
  $("sample-btn").addEventListener("click", function () { area.value = SAMPLE; area.focus(); });
  $("clear-btn").addEventListener("click", function () { area.value = ""; result.hidden = true; last = null; PCH.fieldError(area, $("prompt-error"), ""); area.focus(); });

  function recsText() {
    if (!last) return "";
    return last.recommendations.map(function (r, i) { return (i + 1) + ". " + r; }).join("\n");
  }
  $("copy-recs").addEventListener("click", function () { PCH.copy(recsText() || "No recommendations.", "Recommendations copied."); });
  $("to-improver").addEventListener("click", function () { PCH.handoff.set("improve", lastText || area.value); window.location.href = "/improver"; });

  function txt() {
    var r = last, L = [];
    L.push("PromptCraft Hub - Prompt diagnosis", "=".repeat(36), "", "Score: " + r.score + " / 100 (" + r.label + ")", "Detected type: " + r.use_case_label, "");
    L.push("Components:"); r.components.forEach(function (c) { L.push("- " + c.label + ": " + ({ present: "Present", partial: "Partially present", missing: "Missing", needs_clarification: "Needs clarification" })[c.status]); });
    L.push("", "Checks:"); (r.risk_checks || []).forEach(function (c) { L.push("- " + c.label + ": " + c.summary); });
    L.push("", "Strengths:"); (r.strengths.length ? r.strengths : ["None yet"]).forEach(function (s) { L.push("- " + s); });
    L.push("", "Recommendations:"); r.recommendations.forEach(function (s, i) { L.push((i + 1) + ". " + s); });
    L.push("", "Score breakdown:"); r.breakdown.forEach(function (b) { L.push("- " + b.label + ": " + b.points + "/" + b.max); });
    return L.join("\n") + "\n";
  }
  document.querySelectorAll("[data-download]").forEach(function (b) {
    b.addEventListener("click", function () {
      if (!last) return;
      if (b.dataset.download === "json") PCH.download("prompt-diagnosis.json", JSON.stringify(last, null, 2), "application/json");
      else PCH.download("prompt-diagnosis.txt", txt(), "text/plain");
    });
  });

  var h = PCH.handoff.take("diagnose");
  if (h) { area.value = h; run(h); }
})();
