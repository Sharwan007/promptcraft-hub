/* Before & After: send examples to the Diagnostic or the Builder. */
(function () {
  "use strict";
  var PCH = window.PCH;
  document.addEventListener("click", function (e) {
    var item = e.target.closest(".ba-item");
    if (!item) return;
    if (e.target.closest("[data-diagnose-weak]")) {
      PCH.handoff.set("diagnose", item.querySelector("[data-weak]").textContent); window.location.href = "/diagnostic";
    }
    var tb = e.target.closest("[data-try-builder]");
    if (tb) {
      var text = item.querySelector("[data-improved]").textContent;
      PCH.busy(tb, true, "Opening...");
      PCH.post("/api/prompts/parse", { text: text }).then(function (parts) { PCH.handoff.set("builder", parts); window.location.href = "/builder"; },
        function (err) { PCH.toast(PCH.errorText(err), "error"); PCH.busy(tb, false); });
    }
  });
})();
