(() => {
  const slides = Array.from(document.querySelectorAll(".slide"));
  const stage = document.querySelector(".stage");
  const prev = document.getElementById("prev");
  const next = document.getElementById("next");
  const count = document.getElementById("count");
  let index = 0;

  function show(target) {
    index = Math.max(0, Math.min(slides.length - 1, target));
    slides.forEach((slide, i) => slide.classList.toggle("active", i === index));
    count.textContent = `${index + 1} / ${slides.length}`;
    prev.disabled = index === 0;
    next.disabled = index === slides.length - 1;
    history.replaceState(null, "", `#${index + 1}`);
  }

  function fit() {
    const box = document.querySelector(".viewport").getBoundingClientRect();
    const scale = Math.min((box.width - 48) / 1280, (box.height - 32) / 720);
    stage.style.transform = `scale(${Math.max(scale, 0.2)})`;
  }

  prev.addEventListener("click", () => show(index - 1));
  next.addEventListener("click", () => show(index + 1));
  document.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLButtonElement && (event.key === " " || event.key === "Enter")) return;
    if (["ArrowRight", "PageDown", " "].includes(event.key)) { event.preventDefault(); show(index + 1); }
    else if (["ArrowLeft", "PageUp"].includes(event.key)) { event.preventDefault(); show(index - 1); }
    else if (event.key === "Home") show(0);
    else if (event.key === "End") show(slides.length - 1);
    else if (event.key === "n" || event.key === "N") document.body.classList.toggle("show-notes");
  });
  window.addEventListener("resize", fit);

  const start = parseInt(location.hash.slice(1), 10);
  fit();
  show(Number.isNaN(start) ? 0 : start - 1);
})();
