/* My Prompts: create, edit (versions), archive, restore, permanent delete, version history. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var dataEl = document.getElementById("custom-data");
  if (!dataEl) return;
  var items = {}; JSON.parse(dataEl.textContent).forEach(function (c) { items[c.id] = c; });
  var dlg = document.getElementById("edit-dialog"), form = document.getElementById("edit-form"), editing = null;
  var $ = function (id) { return document.getElementById(id); };

  function openEditor(item) {
    editing = item || null;
    $("edit-title").textContent = item ? "Edit prompt" : "New prompt";
    $("e-title").value = item ? item.title : ""; $("e-desc").value = item ? item.description : "";
    $("e-cat").value = item && item.category_id ? String(item.category_id) : ""; $("e-tags").value = item ? (item.tags || []).join(", ") : "";
    $("e-content").value = item ? item.content : ""; $("e-note").value = ""; $("note-wrap").hidden = !item;
    form.querySelectorAll("[data-err]").forEach(function (e) { e.hidden = true; });
    dlg.showModal(); $("e-title").focus();
  }
  ["new-prompt", "new-prompt-2"].forEach(function (id) { var b = $(id); if (b) b.addEventListener("click", function () { openEditor(null); }); });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var title = $("e-title").value.trim(), content = $("e-content").value.trim(), bad = false;
    PCH.fieldError($("e-title"), form.querySelector('[data-err="title"]'), title.length < 2 ? "Enter a title (at least 2 characters)." : ""); bad = bad || title.length < 2;
    PCH.fieldError($("e-content"), form.querySelector('[data-err="content"]'), content.length < 5 ? "Enter the prompt text (at least 5 characters)." : ""); bad = bad || content.length < 5;
    if (bad) return;
    var body = { title: title, description: $("e-desc").value.trim(), content: content, category_id: $("e-cat").value ? Number($("e-cat").value) : null,
      tags: PCH.comma($("e-tags").value), change_note: $("e-note").value.trim() };
    if (editing) { body.source_prompt_id = editing.source_prompt_id; body.origin = editing.origin; }
    var btn = $("e-save"); PCH.busy(btn, true, "Saving...");
    (editing ? PCH.put("/api/custom-prompts/" + editing.id, body) : PCH.post("/api/custom-prompts", body))
      .then(function () { PCH.reload(editing ? "Prompt saved." : "Prompt created."); },
        function (err) { PCH.toast(PCH.errorText(err), "error"); PCH.busy(btn, false); });
  });

  function versionsDialog(item) {
    var body = $("versions-body"); body.innerHTML = '<p><span class="spinner"></span> Loading...</p>';
    $("versions-dialog").showModal();
    PCH.get("/api/custom-prompts/" + item.id + "/versions").then(function (vs) {
      body.innerHTML = "";
      vs.forEach(function (v, i) {
        var d = PCH.el("div", { "class": "card card-flat", style: "margin-bottom:.75rem" });
        var head = PCH.el("div", { "class": "row between" });
        head.appendChild(PCH.el("strong", { text: "Version " + v.version + (i === 0 ? " (current)" : "") + " - " + v.title }));
        head.appendChild(PCH.el("span", { "class": "small muted", text: new Date(v.created_at + "Z").toLocaleString() + (v.change_note ? " | " + v.change_note : "") }));
        d.appendChild(head);
        d.appendChild(PCH.el("pre", { "class": "prompt-box", style: "max-height:160px;margin:.5rem 0", text: v.content }));
        if (i !== 0) {
          var b = PCH.el("button", { type: "button", "class": "btn btn-secondary btn-sm", text: "Restore this version" });
          b.addEventListener("click", function () {
            PCH.confirm("Restore version " + v.version + "? It becomes a new version; nothing is lost.", { title: "Restore version", ok: "Restore", danger: false }).then(function (ok) {
              if (!ok) return;
              PCH.post("/api/custom-prompts/" + item.id + "/versions/" + v.version + "/restore").then(function () { PCH.reload("Version " + v.version + " restored."); },
                function (e) { PCH.toast(PCH.errorText(e), "error"); });
            });
          });
          d.appendChild(b);
        }
        body.appendChild(d);
      });
    }, function (e) { body.textContent = PCH.errorText(e); });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-act]"); if (!btn) return;
    var card = btn.closest("[data-custom-id]"); if (!card) return;
    var item = items[card.dataset.customId]; if (!item) return;
    var act = btn.dataset.act;
    if (act === "copy") PCH.copy(item.content, "Prompt copied.");
    else if (act === "edit") openEditor(item);
    else if (act === "versions") versionsDialog(item);
    else if (act === "archive") PCH.confirm("Archive \u201C" + item.title + "\u201D? You can restore it later from the Archived tab.", { title: "Archive prompt", ok: "Archive", danger: false }).then(function (ok) {
      if (ok) PCH.post("/api/custom-prompts/" + item.id + "/archive").then(function () { PCH.reload("Prompt archived."); }, function (er) { PCH.toast(PCH.errorText(er), "error"); });
    });
    else if (act === "restore") PCH.post("/api/custom-prompts/" + item.id + "/restore").then(function () { PCH.reload("Prompt restored."); }, function (er) { PCH.toast(PCH.errorText(er), "error"); });
    else if (act === "delete") PCH.confirm("Permanently delete \u201C" + item.title + "\u201D and all " + item.version + " version(s)? This cannot be undone.", { title: "Delete permanently", ok: "Delete permanently" }).then(function (ok) {
      if (ok) PCH.del("/api/custom-prompts/" + item.id + "?permanent=true").then(function () { PCH.reload("Prompt deleted permanently."); }, function (er) { PCH.toast(PCH.errorText(er), "error"); });
    });
  });
})();
