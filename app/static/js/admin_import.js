/* Import preview / commit and backup. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var form = document.getElementById("import-form");
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  var previewed = false;

  function fd(action) {
    var f = $("imp-file").files[0], d = new FormData();
    d.append("file", f); d.append("action", action);
    d.append("duplicates", form.querySelector('input[name="dups"]:checked').value);
    d.append("on_error", form.querySelector('input[name="onerr"]:checked').value);
    return d;
  }
  function chosen() {
    var f = $("imp-file").files[0], err = $("imp-error");
    if (!f) { PCH.fieldError($("imp-file"), err, "Choose a .json file first."); return null; }
    if (!/\.json$/i.test(f.name)) { PCH.fieldError($("imp-file"), err, "Only .json files can be imported."); return null; }
    PCH.fieldError($("imp-file"), err, ""); return f;
  }
  function show(r, committed) {
    $("import-result").hidden = false;
    var s = r.summary || {};
    var html = committed
      ? '<div class="alert ' + (r.status === "completed" ? "alert-success" : "alert-danger") + '" role="status"><div><strong>' + PCH.escape(r.message) + '</strong></div></div>'
      : '<div class="alert alert-info" role="status"><div><strong>' + r.total + ' prompt(s) checked:</strong> ' + (s.new || 0) + ' new, ' + (s.duplicate || 0) + ' duplicate, ' + (s.invalid || 0) + ' invalid.</div></div>';
    $("import-summary").innerHTML = html;
    var tb = $("import-rows"); tb.innerHTML = "";
    (r.items || []).forEach(function (it) {
      var cls = it.status === "new" ? "badge-present" : (it.status === "duplicate" ? "badge-partial" : "badge-missing");
      var tr = PCH.el("tr", {});
      tr.innerHTML = "<td>" + it.index + "</td><td>" + PCH.escape(it.title) + "</td><td class='mono small'>" + PCH.escape(it.slug || "") + "</td><td><span class='badge " + cls + "'>" + PCH.escape(it.status) + "</span></td><td class='small'>" + PCH.escape((it.errors || []).join(" | ")) + "</td>";
      tb.appendChild(tr);
    });
    $("import-download").innerHTML = (committed && r.history_id && (r.status === "aborted" || r.skipped))
      ? '<a class="btn btn-secondary" href="/api/admin/imports/' + r.history_id + '/errors" download>Download import-error report</a>' : "";
  }
  $("imp-file").addEventListener("change", function () { previewed = false; $("commit-btn").disabled = true; });
  $("preview-btn").addEventListener("click", function () {
    if (!chosen()) return;
    var b = $("preview-btn"); PCH.busy(b, true, "Validating...");
    PCH.api("POST", "/api/import", fd("preview")).then(function (r) {
      show(r, false); previewed = true; $("commit-btn").disabled = false;
      if (r.summary && r.summary.invalid) PCH.toast("The file contains invalid prompts. Review the table before importing.", "error"); else PCH.toast("The file is valid.", "success");
    }, function (e) { PCH.fieldError($("imp-file"), $("imp-error"), PCH.errorText(e)); previewed = false; $("commit-btn").disabled = true; })
      .then(function () { PCH.busy(b, false); });
  });
  $("commit-btn").addEventListener("click", function () {
    if (!chosen() || !previewed) { PCH.toast("Preview the file first.", "info"); return; }
    PCH.confirm("Import the prompts from this file now?", { title: "Import prompts", ok: "Import", danger: false }).then(function (ok) {
      if (!ok) return;
      var b = $("commit-btn"); PCH.busy(b, true, "Importing...");
      PCH.api("POST", "/api/import", fd("commit")).then(function (r) { show(r, true); PCH.toast(r.message, r.status === "completed" ? "success" : "error", 6000); },
        function (e) { PCH.toast(PCH.errorText(e), "error"); }).then(function () { PCH.busy(b, false); });
    });
  });
  $("backup-btn").addEventListener("click", function () {
    var b = $("backup-btn"); PCH.busy(b, true, "Backing up...");
    PCH.post("/api/backup").then(function (r) { PCH.toast(r.message + " Saved as " + r.file + ".", "success", 7000); }, function (e) { PCH.toast(PCH.errorText(e), "error"); })
      .then(function () { PCH.busy(b, false); });
  });
})();
