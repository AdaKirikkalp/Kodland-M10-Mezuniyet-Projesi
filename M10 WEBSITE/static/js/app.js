document.addEventListener("DOMContentLoaded", () => {
  const menu = document.querySelector(".menu-toggle");
  const nav = document.querySelector(".main-nav");
  if (menu && nav) {
    menu.addEventListener("click", () => {
      const open = nav.classList.toggle("is-open");
      menu.setAttribute("aria-expanded", String(open));
    });
  }

  document.querySelectorAll(".choice-card input").forEach((input) => {
    const sync = () => input.closest(".choice-card")?.classList.toggle("is-selected", input.checked);
    input.addEventListener("change", sync);
    sync();
  });

  document.querySelectorAll(".flash").forEach((flash) => {
    window.setTimeout(() => {
      flash.classList.add("is-leaving");
      window.setTimeout(() => flash.remove(), 300);
    }, 6500);
  });

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduceMotion) {
    document.querySelectorAll(".story-card, .impact-item, .feedback-card, .history-row").forEach((item, index) => {
      item.style.setProperty("--reveal-delay", `${Math.min(index * 45, 220)}ms`);
      item.classList.add("reveal-ready");
    });
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });
    document.querySelectorAll(".reveal-ready").forEach((item) => observer.observe(item));
  }
});
