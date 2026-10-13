/* Applies the saved theme before first paint (no flash). Loaded synchronously in <head>. */
(function () {
  try {
    var pref = localStorage.getItem("pch-theme") || "system";
    var dark = pref === "dark" || (pref === "system" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  } catch (e) { document.documentElement.setAttribute("data-theme", "light"); }
})();
