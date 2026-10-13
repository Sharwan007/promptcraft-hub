/* Settings: profile + preferences, reset helpers. */
(function () {
  "use strict";
  var PCH = window.PCH;
  var form = document.getElementById("settings-form");
  if (!form) return;
  var $ = function (id) { return document.getElementById(id); };
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var name = $("s-name").value.trim();
    PCH.fieldError($("s-name"), $("s-name-err"), name ? "" : "Display name cannot be empty.");
    if (!name) return;
    var body = { display_name: name, role: $("s-role").value.trim(), theme: $("s-theme").value, view_mode: $("s-view").value, default_ai_tool: $("s-tool").value };
    PCH.put("/api/settings", body).then(function (s) {
      try { localStorage.setItem("pch-theme", s.theme); } catch (er) { /* ignore */ }
      var dark = s.theme === "dark" || (s.theme === "system" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
      PCH.toast("Settings saved.", "success");
    }, function (er) { PCH.toast(PCH.errorText(er), "error"); });
  });
  $("reset-progress").addEventListener("click", function () {
    PCH.confirm("Reset all learning progress? Lessons will show as not started.", { title: "Reset learning progress", ok: "Reset" }).then(function (ok) {
      if (!ok) return;
      PCH.get("/api/learning/progress").then(function (p) {
        return Promise.all((p.completed_ids || []).map(function (id) { return PCH.post("/api/learning/progress", { module_id: id, completed: false }); }));
      }).then(function () { PCH.toast("Learning progress reset.", "success"); }, function (er) { PCH.toast(PCH.errorText(er), "error"); });
    });
  });
  $("clear-drafts").addEventListener("click", function () {
    try { localStorage.removeItem("pch-builder-draft"); localStorage.removeItem("pch-builder-autosave"); } catch (e) { /* ignore */ }
    PCH.toast("Saved builder drafts were cleared from this browser.", "success");
  });
})();
