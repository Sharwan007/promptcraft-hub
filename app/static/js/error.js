(function () { var b = document.getElementById("go-back"); if (b) b.addEventListener("click", function () { if (history.length > 1) history.back(); else window.location.href = "/"; }); })();
