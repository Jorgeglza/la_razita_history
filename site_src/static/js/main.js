(function () {
  "use strict";

  // ---- Active nav link highlighting on scroll ----
  var sections = Array.prototype.slice.call(document.querySelectorAll("section[id]"));
  var navLinks = Array.prototype.slice.call(document.querySelectorAll(".topnav nav a"));

  function onScroll() {
    var scrollPos = window.scrollY + 90;
    var current = sections[0] && sections[0].id;
    sections.forEach(function (sec) {
      if (sec.offsetTop <= scrollPos) current = sec.id;
    });
    navLinks.forEach(function (a) {
      a.classList.toggle("active", a.getAttribute("href") === "#" + current);
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // ---- Sortable tables: click a <th data-sort-key> to sort its table ----
  // Tables marked data-paired-rows have each data row immediately followed by
  // a hidden "detail" row (class standings-detail) that must move with it.
  document.querySelectorAll("table[data-sortable]").forEach(function (table) {
    var tbody = table.querySelector("tbody");
    var paired = table.hasAttribute("data-paired-rows");
    var headers = Array.prototype.slice.call(table.querySelectorAll("th[data-sort-key]"));
    headers.forEach(function (th) {
      th.addEventListener("click", function () {
        var key = th.getAttribute("data-sort-key");
        var type = th.getAttribute("data-sort-type") || "string";
        var asc = th.getAttribute("data-sort-dir") !== "asc";
        headers.forEach(function (h) {
          h.classList.remove("sorted");
          h.removeAttribute("data-sort-dir");
        });
        th.classList.add("sorted");
        th.setAttribute("data-sort-dir", asc ? "asc" : "desc");

        // Direct children only — a paired table's detail rows contain their
        // own nested <table> with <tr>s that must NOT be swept up here.
        var allRows = Array.prototype.filter.call(tbody.children, function (el) {
          return el.tagName === "TR";
        });
        var rows, detailFor;
        if (paired) {
          rows = allRows.filter(function (r) { return !r.classList.contains("standings-detail"); });
          detailFor = new Map();
          rows.forEach(function (r) {
            var next = r.nextElementSibling;
            if (next && next.classList.contains("standings-detail")) detailFor.set(r, next);
          });
        } else {
          rows = allRows;
        }

        rows.sort(function (a, b) {
          var av = a.querySelector("[data-" + key + "]").getAttribute("data-" + key);
          var bv = b.querySelector("[data-" + key + "]").getAttribute("data-" + key);
          if (type === "number") {
            av = parseFloat(av) || 0;
            bv = parseFloat(bv) || 0;
          }
          if (av < bv) return asc ? -1 : 1;
          if (av > bv) return asc ? 1 : -1;
          return 0;
        });
        rows.forEach(function (r) {
          tbody.appendChild(r);
          if (paired && detailFor.has(r)) tbody.appendChild(detailFor.get(r));
        });
      });
    });

    // ---- Click-to-expand: paired tables reveal a detail row per row ----
    if (paired) {
      tbody.querySelectorAll("tr.standings-row").forEach(function (row) {
        var detail = row.nextElementSibling;
        if (!detail || !detail.classList.contains("standings-detail")) return;
        var caret = row.querySelector(".expand-caret");
        function toggle() {
          var open = !detail.hidden;
          detail.hidden = open;
          row.setAttribute("aria-expanded", String(!open));
          row.classList.toggle("expanded", !open);
          if (caret) caret.textContent = open ? "▸" : "▾";
        }
        row.addEventListener("click", toggle);
        row.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
        });
      });
    }
  });

  // ---- Draft countdown ----
  var countdownEl = document.getElementById("draft-countdown");
  if (countdownEl) {
    var target = new Date(countdownEl.getAttribute("data-target"));
    var elDays = countdownEl.querySelector("[data-unit='days']");
    var elHours = countdownEl.querySelector("[data-unit='hours']");
    var elMins = countdownEl.querySelector("[data-unit='minutes']");
    var elSecs = countdownEl.querySelector("[data-unit='seconds']");

    function tick() {
      var diff = target.getTime() - Date.now();
      if (isNaN(target.getTime())) return;
      if (diff <= 0) {
        countdownEl.querySelector(".countdown-label").textContent = "Draft day is here (or already happened)";
        elDays.textContent = elHours.textContent = elMins.textContent = elSecs.textContent = "00";
        return;
      }
      var d = Math.floor(diff / 86400000);
      var h = Math.floor((diff % 86400000) / 3600000);
      var m = Math.floor((diff % 3600000) / 60000);
      var s = Math.floor((diff % 60000) / 1000);
      elDays.textContent = String(d).padStart(2, "0");
      elHours.textContent = String(h).padStart(2, "0");
      elMins.textContent = String(m).padStart(2, "0");
      elSecs.textContent = String(s).padStart(2, "0");
    }
    tick();
    setInterval(tick, 1000);
  }
})();
