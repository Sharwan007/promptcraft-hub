/* Favorite toggles for every prompt card and detail page. */
(function () {
  "use strict";
  var PCH = window.PCH;
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-favorite]");
    if (!btn || btn.disabled) return;
    var id = btn.getAttribute("data-favorite");
    var on = btn.getAttribute("aria-pressed") === "true";
    btn.disabled = true;
    (on ? PCH.del("/api/favorites/" + id) : PCH.post("/api/favorites/" + id)).then(function () {
      var now = !on;
      document.querySelectorAll('[data-favorite="' + id + '"]').forEach(function (b) {
        b.setAttribute("aria-pressed", now ? "true" : "false");
        b.classList.toggle("is-on", now);
        var label = b.getAttribute("aria-label") || "";
        b.setAttribute("aria-label", label.replace(/^(Add to|Remove from) favorites/, now ? "Remove from favorites" : "Add to favorites"));
        var span = b.querySelector("[data-fav-label]"); if (span) span.textContent = now ? "Favorited" : "Favorite";
      });
      PCH.toast(now ? "Added to favorites." : "Removed from favorites.", "success", 2200);
      var coll = document.querySelector("[data-remove-on-unfavorite]");
      if (coll && !now) {
        var wrap = btn.closest("[data-fav-wrap]"); if (wrap) wrap.remove();
        if (!coll.querySelector("[data-fav-wrap]")) PCH.reload();
      }
    }).catch(function (err) { PCH.toast(PCH.errorText(err), "error"); }).then(function () { btn.disabled = false; });
  });
})();
