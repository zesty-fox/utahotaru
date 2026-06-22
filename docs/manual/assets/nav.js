// StrangeUtaGame 说明书 · 侧边栏交互
(function () {
  // 高亮当前页
  var here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav-group a").forEach(function (a) {
    var href = a.getAttribute("href");
    if (href === here) a.classList.add("active");
  });

  // 移动端菜单开关
  var btn = document.querySelector(".menu-toggle");
  var sb = document.querySelector(".sidebar");
  if (btn && sb) {
    btn.addEventListener("click", function () { sb.classList.toggle("open"); });
    document.querySelector(".content").addEventListener("click", function () {
      sb.classList.remove("open");
    });
  }
})();
