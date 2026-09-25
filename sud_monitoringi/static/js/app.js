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
          backgroundColor: type === "line" ? "rgba(42,157,143,.15)" : items.map(function (_, idx) { return opts.single ? "#1f5fae" : palette[idx % palette.length]; }),
          borderColor: type === "line" ? "#2a9d8f" : "#fff",
          borderWidth: type === "line" ? 2 : 1,
          fill: type === "line",
          tension: .3,
          pointRadius: 4,
          borderRadius: type === "bar" || horizontal ? 4 : 0
        }]
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
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
    return chart;
  };
})();
