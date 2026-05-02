// Sigil dashboard: pulse numeric cells when their value changed since the
// previous page render. Pairs with .tick-pulse-up / .tick-pulse-down CSS
// keyframes in dashboard.css.
//
// Server-rendered numbers go in elements like:
//   <span data-tick-key="markets/{ext_id}/last" data-tick-value="0.475">0.475</span>
//
// On DOMContentLoaded we look up each tick-key's previous value in
// localStorage. If the value changed, add `tick-pulse-up` (new > prev) or
// `tick-pulse-down` (new < prev) for the duration of the CSS animation.
// Then write the new value back to localStorage so the next refresh has a
// reference point.
//
// First page load = nothing in localStorage = no pulse. Refresh = pulse on
// any cell whose value actually moved.
(function () {
  var STORAGE_PREFIX = "sigil:tick:";
  var ANIMATION_MS = 1800; // matches CSS animation-duration

  function readPrev(key) {
    try {
      return localStorage.getItem(STORAGE_PREFIX + key);
    } catch (e) {
      return null;
    }
  }
  function writeNext(key, value) {
    try {
      localStorage.setItem(STORAGE_PREFIX + key, value);
    } catch (e) {}
  }

  function paint() {
    var nodes = document.querySelectorAll("[data-tick-value][data-tick-key]");
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var key = node.getAttribute("data-tick-key");
      var raw = node.getAttribute("data-tick-value");
      if (!key || raw == null) continue;
      var nextNum = parseFloat(raw);
      if (isNaN(nextNum)) continue;
      var prevRaw = readPrev(key);
      writeNext(key, raw);
      if (prevRaw == null) continue;
      var prevNum = parseFloat(prevRaw);
      if (isNaN(prevNum)) continue;
      if (nextNum === prevNum) continue;
      var cls = nextNum > prevNum ? "tick-pulse-up" : "tick-pulse-down";
      // Re-trigger animation by removing then re-adding on next frame.
      node.classList.remove("tick-pulse-up", "tick-pulse-down");
      // eslint-disable-next-line no-unused-expressions
      void node.offsetWidth;
      node.classList.add(cls);
      // Strip the class once the animation finishes so successive refreshes
      // re-pulse cleanly even when the value bounces.
      (function (n, c) {
        setTimeout(function () { n.classList.remove(c); }, ANIMATION_MS);
      })(node, cls);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", paint);
  } else {
    paint();
  }
})();
