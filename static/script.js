document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();

  const toggle = document.querySelector("[data-menu-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const opened = nav.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", String(opened));
      if (window.lucide) window.lucide.createIcons();
    });
  }

  document.querySelectorAll("form[data-confirm]").forEach(form => {
    form.addEventListener("submit", event => {
      if (!window.confirm(form.dataset.confirm || "Continue?")) event.preventDefault();
    });
  });

  document.querySelectorAll('input[type="date"]').forEach(input => {
    if (!input.min) {
      const today = new Date();
      const local = new Date(today.getTime() - today.getTimezoneOffset() * 60000);
      input.min = local.toISOString().slice(0, 10);
    }
  });

  document.querySelectorAll(".flash").forEach(message => {
    window.setTimeout(() => {
      message.classList.add("flash-hide");
      window.setTimeout(() => message.remove(), 350);
    }, 5000);
  });
});
