/* Learning Center: glossary filter, knowledge checks, completion tracking. */
(function () {
  "use strict";
  var PCH = window.PCH;

  var gf = document.getElementById("gloss-filter");
  if (gf) gf.addEventListener("input", PCH.debounce(function () {
    var q = gf.value.trim().toLowerCase(), shown = 0;
    document.querySelectorAll("#gloss-list [data-term]").forEach(function (d) { var m = !q || d.dataset.term.indexOf(q) !== -1; d.hidden = !m; if (m) shown++; });
    document.getElementById("gloss-empty").hidden = shown > 0;
  }, 150));

  document.querySelectorAll(".quiz-q").forEach(function (q) {
    var correct = Number(q.dataset.correct), fb = q.querySelector("[data-feedback]");
    q.querySelectorAll(".quiz-opt").forEach(function (b) {
      b.addEventListener("click", function () {
        q.querySelectorAll(".quiz-opt").forEach(function (x) { x.classList.remove("is-right", "is-wrong"); });
        var ok = Number(b.dataset.index) === correct;
        b.classList.add(ok ? "is-right" : "is-wrong");
        fb.textContent = (ok ? "Correct. " : "Not quite. ") + (q.dataset.explanation || "");
      });
    });
  });

  var btn = document.getElementById("complete-btn");
  if (btn) btn.addEventListener("click", function () {
    var done = btn.dataset.completed === "true";
    PCH.busy(btn, true, "Saving...");
    PCH.post("/api/learning/progress", { module_id: Number(btn.dataset.moduleId), completed: !done }).then(function () {
      PCH.reload(done ? "Lesson marked as not complete." : "Lesson completed. Nice work!", "success");
    }, function (e) { PCH.toast(PCH.errorText(e), "error"); PCH.busy(btn, false); });
  });
})();
