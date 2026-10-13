/* Administration dashboard: prompt table, quick actions, backup, PIN change. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var rows = document.getElementById("admin-rows");
  if (!rows) return;
  var $ = function (id) { return document.getElementById(id); };
  var page = 1, pages = 1;

  function status(p) {
    var s = [];
    s.push(p.archived ? '<span class="badge badge-draft">Archived</span>' : (p.published ? '<span class="badge badge-present">Published</span>' : '<span class="badge badge-partial">Unpublished</span>'));
    if (p.featured) s.push('<span class="badge badge-featured">Featured</span>');
    return s.join(" ");
  }
  function load() {
    var qs = new URLSearchParams({ page: page, page_size: 12 });
    if ($("a-q").value.trim()) qs.set("q", $("a-q").value.trim());
    if ($("a-status").value) qs.set("status", $("a-status").value);
    if ($("a-cat").value) qs.set("category", $("a-cat").value);
    rows.classList.add("loading");
    PCH.get("/api/admin/prompts?" + qs.toString()).then(function (r) {
      pages = r.pages; rows.innerHTML = "";
      if (!r.items.length) rows.innerHTML = '<tr><td colspan="5" class="muted">No prompts match these filters.</td></tr>';
      r.items.forEach(function (p) {
        var tr = PCH.el("tr", {});
        tr.innerHTML = '<td><a href="/prompts/' + PCH.escape(p.slug) + '"><strong>' + PCH.escape(p.title) + '</strong></a><div class="small muted">' + PCH.escape(p.difficulty) + '</div></td><td>' + PCH.escape(p.category) + '</td><td>' + status(p) + '</td><td>' + p.view_count + '</td><td></td>';
        var actions = tr.lastElementChild; actions.className = "nowrap";
        var mk = function (label, fn, cls) { var b = PCH.el("button", { type: "button", "class": "btn btn-secondary btn-sm " + (cls || ""), text: label, style: "margin:0 .25rem .25rem 0" }); b.addEventListener("click", fn); actions.appendChild(b); };
        actions.appendChild(PCH.el("a", { "class": "btn btn-primary btn-sm", href: "/admin/prompts/" + p.id + "/edit", text: "Edit", style: "margin:0 .25rem .25rem 0" }));
        var flag = function (body, msg) { return function () { PCH.patch("/api/prompts/" + p.id + "/flags", body).then(function () { PCH.toast(msg, "success"); load(); }, function (e) { PCH.toast(PCH.errorText(e), "error"); }); }; };
        if (p.archived) { mk("Restore", flag({ archived: false }, "Prompt restored.")); mk("Delete permanently", function () {
          PCH.confirm("Permanently delete \u201C" + p.title + "\u201D? This cannot be undone.", { title: "Delete permanently", ok: "Delete permanently" }).then(function (ok) {
            if (ok) PCH.del("/api/prompts/" + p.id + "?permanent=true").then(function () { PCH.toast("Prompt deleted permanently.", "success"); load(); }, function (e) { PCH.toast(PCH.errorText(e), "error"); });
          }); }, "btn-danger"); }
        else {
          mk(p.published ? "Unpublish" : "Publish", flag({ published: !p.published }, p.published ? "Prompt unpublished." : "Prompt published."));
          mk(p.featured ? "Unfeature" : "Feature", flag({ featured: !p.featured }, p.featured ? "Removed from featured." : "Marked as featured."));
          mk("Archive", function () { PCH.confirm("Archive \u201C" + p.title + "\u201D? It disappears from the library but can be restored.", { title: "Archive prompt", ok: "Archive", danger: false }).then(function (ok) { if (ok) flag({ archived: true }, "Prompt archived.")(); }); });
        }
        rows.appendChild(tr);
      });
      $("admin-count").textContent = r.total + " prompt(s) | page " + r.page + " of " + r.pages;
      $("a-prev").disabled = r.page <= 1; $("a-next").disabled = r.page >= r.pages;
    }, function (e) { rows.innerHTML = '<tr><td colspan="5" class="error-text">' + PCH.escape(PCH.errorText(e)) + '</td></tr>'; })
      .then(function () { rows.classList.remove("loading"); });
  }
  var soon = PCH.debounce(function () { page = 1; load(); }, 300);
  $("a-q").addEventListener("input", soon); $("a-status").addEventListener("change", soon); $("a-cat").addEventListener("change", soon);
  $("admin-filter").addEventListener("submit", function (e) { e.preventDefault(); });
  $("a-prev").addEventListener("click", function () { if (page > 1) { page--; load(); } });
  $("a-next").addEventListener("click", function () { if (page < pages) { page++; load(); } });
  load();

  $("backup-btn").addEventListener("click", function () {
    var b = $("backup-btn"); PCH.busy(b, true, "Backing up...");
    PCH.post("/api/backup").then(function (r) { PCH.toast(r.message + " Saved as " + r.file + ".", "success", 7000); var li = PCH.el("li", {}); li.textContent = r.file + " (" + r.size_kb + " KB)"; $("backup-list").prepend(li); },
      function (e) { PCH.toast(PCH.errorText(e), "error"); }).then(function () { PCH.busy(b, false); });
  });

  var dlg = $("pin-dialog"), pform = $("pin-form");
  $("pin-btn").addEventListener("click", function () { $("pin-error").hidden = true; pform.reset(); dlg.showModal(); $("p-cur").focus(); });
  pform.addEventListener("submit", function (e) {
    e.preventDefault();
    PCH.post("/api/admin/change-pin", { current: $("p-cur").value, "new": $("p-new").value, confirm: $("p-conf").value }).then(function () { dlg.close(); PCH.toast("PIN changed. Other sessions were signed out.", "success"); },
      function (er) { $("pin-error").textContent = PCH.errorText(er); $("pin-error").hidden = false; });
  });
})();
