(function () {
  // Mobil qurilmalarda yon panelni ochish/yopish
  document.addEventListener("click", function (e) {
    var toggle = e.target.closest("[data-sidebar-toggle]");
    var sidebar = document.querySelector(".sm-sidebar");
    if (toggle && sidebar) {
      sidebar.classList.toggle("show");
      return;
    }
    if (sidebar && sidebar.classList.contains("show") && !e.target.closest(".sm-sidebar")) {
      sidebar.classList.remove("show");
    }
    // Jadval qatori bosilganda havolaga o'tish
    var row = e.target.closest("tr[data-href]");
    if (row && !e.target.closest("a, button, input, form")) {
      window.location = row.getAttribute("data-href");
    }
  });

  // Tasdiqlash so'raladigan formalar
  document.addEventListener("submit", function (e) {
    var msg = e.target.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) {
      e.preventDefault();
    }
  });

  // Dashboard diagrammalari: ustiga bosilganda tegishli ishlar ro'yxati ochiladi
  var palette = ["#1f5fae", "#2a9d8f", "#e9a23b", "#c0392b", "#6f42c1", "#3a86ff", "#8d99ae", "#43aa8b", "#f3722c", "#577590", "#90be6d", "#b5838d"];
  window.smChart = function (canvasId, dataId, type, opts) {
    var el = document.getElementById(canvasId);
    var src = document.getElementById(dataId);
    if (!el || !src || typeof Chart === "undefined") return;
    var items = JSON.parse(src.textContent);
    opts = opts || {};
    var horizontal = type === "hbar";
    var chart = new Chart(el, {
      type: horizontal ? "bar" : type,
      data: {
        labels: items.map(function (i) { return i.label; }),
        datasets: [{
          data: items.map(function (i) { return i.value; }),
          backgroundColor: type === "line" ? (opts.line ? opts.line + "26" : "rgba(42,157,143,.15)") : items.map(function (_, idx) { var pal = opts.colors || palette; return opts.single ? "#1f5fae" : pal[idx % pal.length]; }),
          borderColor: type === "line" ? (opts.line || "#2a9d8f") : (opts.colors ? "transparent" : "#fff"),
          borderWidth: type === "line" ? 2 : 1,
          fill: type === "line",
          tension: .3,
          pointRadius: 4,
          borderRadius: type === "bar" || horizontal ? 4 : 0
        }]
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        animation: { duration: 1400, easing: "easeOutQuart" },
        maintainAspectRatio: false,
        plugins: {
          legend: { display: type === "doughnut" || type === "pie", position: opts.legendBottom ? "bottom" : "right", labels: { boxWidth: 12, font: { size: 11 } } },
          tooltip: { callbacks: { footer: function () { return "Batafsil ko‘rish uchun bosing"; } } }
        },
        scales: (type === "doughnut" || type === "pie") ? {} : {
          x: { ticks: { font: { size: 11 }, autoSkip: !horizontal }, beginAtZero: true },
          y: { ticks: { font: { size: 11 }, precision: 0 }, beginAtZero: true }
        },
        onClick: function (evt, elements) {
          if (elements.length) {
            var item = items[elements[0].index];
            if (item && item.url) window.location = item.url;
          }
        },
        onHover: function (evt, elements) {
          evt.native.target.style.cursor = elements.length ? "pointer" : "default";
        }
      }
    });
    if (opts.cutout && chart.options) { chart.options.cutout = opts.cutout; chart.update("none"); }
    return chart;
  };
})();

// Raqamlarni 0 dan sanab chiqish animatsiyasi: <span data-countup="123">123</span>
(function () {
  function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function run() {
    var els = document.querySelectorAll("[data-countup]");
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    els.forEach(function (el) {
      var target = parseFloat(el.getAttribute("data-countup")) || 0;
      var suffix = el.getAttribute("data-suffix") || "";
      if (reduce || target === 0) { el.textContent = fmt(target) + suffix; return; }
      var duration = 1400, start = null;
      el.textContent = "0" + suffix;
      function step(ts) {
        if (!start) start = ts;
        var p = Math.min((ts - start) / duration, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = fmt(Math.round(target * eased)) + suffix;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
    // Gorizontal ko'rsatkich chiziqlari: <span data-width="42"></span>
    requestAnimationFrame(function () {
      document.querySelectorAll("[data-width]").forEach(function (el) { el.style.width = el.getAttribute("data-width") + "%"; });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();

// Xarita: hudud ustiga kelganda ma'lumot oynasi
(function () {
  document.querySelectorAll(".uz-map-wrap").forEach(function (wrap) {
    var tip = wrap.querySelector(".uz-tip");
    function show(link, evt) {
      var p = link.getAttribute("data-tip").split("|");
      var code = link.getAttribute("href");
      wrap.querySelectorAll('.uz-region-link[href="' + code + '"]').forEach(function (a) { a.classList.add("is-hover"); });
      tip.innerHTML = "<b></b><br>Jami: <span></span><br>Jarayonda: <span></span> · Yakunlangan: <span></span>" +
        (p[4] !== "0" ? '<br><span style="color:#ff8787">Muddati o‘tgan nazorat: </span><span></span>' : "");
      var slots = tip.querySelectorAll("b, span:not([style])");
      slots[0].textContent = p[0]; slots[1].textContent = p[1]; slots[2].textContent = p[2]; slots[3].textContent = p[3];
      if (slots[4]) slots[4].textContent = p[4];
      tip.hidden = false;
      move(evt);
    }
    function move(evt) {
      var r = wrap.getBoundingClientRect();
      var x = evt.clientX - r.left + 14, y = evt.clientY - r.top + 14;
      if (x + tip.offsetWidth > r.width) x = evt.clientX - r.left - tip.offsetWidth - 14;
      x = Math.max(4, Math.min(x, r.width - tip.offsetWidth - 4));
      tip.style.left = x + "px"; tip.style.top = y + "px";
    }
    function hide() {
      tip.hidden = true;
      wrap.querySelectorAll(".is-hover").forEach(function (a) { a.classList.remove("is-hover"); });
    }
    wrap.querySelectorAll("[data-tip]").forEach(function (link) {
      link.addEventListener("mouseenter", function (e) { show(link, e); });
      link.addEventListener("mousemove", move);
      link.addEventListener("mouseleave", hide);
    });
  });
})();
