document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".menu-toggle");
  const menu = document.querySelector(".top-links");
  const mobileQuery = window.matchMedia("(max-width: 800px)");

  if (!toggle || !menu) {
    return;
  }

  const syncMenuState = () => {
    const isMobile = mobileQuery.matches;
    menu.hidden = !isMobile || toggle.getAttribute("aria-expanded") !== "true";
    if (!isMobile) {
      toggle.setAttribute("aria-expanded", "false");
      menu.classList.remove("is-open");
      menu.hidden = false;
    }
  };

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    menu.classList.toggle("is-open", !isOpen);
    menu.hidden = isOpen;
  });

  menu.querySelectorAll("a, button").forEach((element) => {
    element.addEventListener("click", () => {
      if (mobileQuery.matches) {
        toggle.setAttribute("aria-expanded", "false");
        menu.classList.remove("is-open");
        menu.hidden = true;
      }
    });
  });

  mobileQuery.addEventListener("change", syncMenuState);
  syncMenuState();
});