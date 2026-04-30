// Sigil dashboard: paint relative timestamps in [data-relative-time] elements.
// No deps, no bundling. Runs on DOMContentLoaded and every 10s thereafter.
(function () {
  function format(diffMs) {
    var s = Math.round(diffMs / 1000);
    if (s < 0) return "just now";
    if (s < 5) return "just now";
    if (s < 60) return s + "s ago";
    var m = Math.round(s / 60);
    if (m < 60) return m + "m ago";
    var h = Math.round(m / 60);
    if (h < 48) return h + "h ago";
    var d = Math.round(h / 24);
    return d + "d ago";
  }

  function paint() {
    var now = Date.now();
    var nodes = document.querySelectorAll("[data-relative-time]");
    for (var i = 0; i < nodes.length; i++) {
      var iso = nodes[i].getAttribute("data-relative-time");
      if (!iso) continue;
      var t = Date.parse(iso);
      if (isNaN(t)) continue;
      nodes[i].textContent = format(now - t);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", paint);
  } else {
    paint();
  }
  setInterval(paint, 10000);
})();
