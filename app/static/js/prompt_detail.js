/* Prompt detail: placeholder customisation with live preview, save, export, duplicate. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var dataEl = document.getElementById("prompt-data");
  if (!dataEl) return;
  var data = JSON.parse(dataEl.textContent);
  var preview = document.getElementById("prompt-preview");
  var fields = Array.prototype.slice.call(document.querySelectorAll("textarea[data-ph]"));
  var RE = /\[([A-Z][A-Z0-9 _\/&\-]{1,40})\]/g;

  function values() { var v = {}; fields.forEach(function (f) { v[f.dataset.ph] = f.value.trim(); }); return v; }
  function customized() {
    var v = values();
    return data.full_prompt.replace(RE, function (m, name) { return v[name] ? v[name] : m; });
  }
  function render() {
    var v = values(), text = data.full_prompt, last = 0, m;
    preview.textContent = "";
    RE.lastIndex = 0;
    while ((m = RE.exec(text)) !== null) {
      preview.appendChild(document.createTextNode(text.slice(last, m.index)));
      var s = document.createElement("span");
      if (v[m[1]]) { s.className = "ph"; s.style.background = "var(--accent-50)"; s.style.color = "var(--accent)"; s.textContent = v[m[1]]; }
      else { s.className = "ph"; s.textContent = m[0]; }
      preview.appendChild(s); last = m.index + m[0].length;
    }
    preview.appendChild(document.createTextNode(text.slice(last)));
  }
  fields.forEach(function (f) { f.addEventListener("input", render); });
  render();

  var copyBtn = document.getElementById("copy-custom");
  if (copyBtn) copyBtn.addEventListener("click", function () {
    PCH.copy(customized(), "Customized prompt copied.").then(function (ok) { if (ok) PCH.post("/api/prompts/" + data.id + "/copy").catch(function () {}); });
  });

  var reset = document.getElementById("reset-custom");
  if (reset) reset.addEventListener("click", function () { fields.forEach(function (f) { f.value = ""; }); render(); PCH.toast("Customization reset.", "info", 1800); });

  var save = document.getElementById("save-custom");
  if (save) save.addEventListener("click", function () {
    PCH.ask("Name for your copy", data.title + " (customized)", { title: "Save to My Prompts" }).then(function (title) {
      if (!title) return;
      PCH.busy(save, true, "Saving...");
      PCH.post("/api/custom-prompts", { title: title, description: data.description, content: customized(), category_id: data.category_id,
        tags: data.tags, source_prompt_id: data.id, origin: "customized" })
        .then(function () { PCH.toast("Saved to My Prompts.", "success"); }, function (e) { PCH.toast(PCH.errorText(e), "error"); })
        .then(function () { PCH.busy(save, false); });
    });
  });

  document.querySelectorAll("[data-export-custom]").forEach(function (b) {
    b.addEventListener("click", function () { PCH.exportPrompt(data.title, customized(), b.dataset.exportCustom); });
  });

  var dup = document.getElementById("duplicate-btn");
  if (dup) dup.addEventListener("click", function () {
    PCH.busy(dup, true, "Copying...");
    PCH.post("/api/custom-prompts/from-prompt/" + data.id, {}).then(function () { PCH.reload && (PCH.flash("A copy was added to My Prompts."), window.location.href = "/my-prompts"); },
      function (e) { PCH.toast(PCH.errorText(e), "error"); PCH.busy(dup, false); });
  });
})();
