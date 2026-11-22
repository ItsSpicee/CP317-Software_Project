(() => {
  const SELECTOR = ".ns-home-charts";
  const watched = new WeakSet();

  const prefersReduced = () =>
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /** Restart so rings always run 0% → intake% when they appear. */
  const play = (root) => {
    root.classList.remove("is-inview");
    void root.offsetWidth;
    requestAnimationFrame(() => {
      root.classList.add("is-inview");
    });
  };

  const observe = (root) => {
    if (!(root instanceof Element) || watched.has(root)) return;
    watched.add(root);

    if (prefersReduced()) {
      root.classList.add("is-inview");
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          play(entry.target);
          io.unobserve(entry.target);
        }
      },
      { threshold: 0.25, rootMargin: "0px 0px -5% 0px" },
    );
    io.observe(root);

    // If already on screen when the section mounts, animate immediately.
    const rect = root.getBoundingClientRect();
    if (rect.top < window.innerHeight * 0.9 && rect.bottom > 40) {
      play(root);
      io.unobserve(root);
    }
  };

  const scan = () => {
    document.querySelectorAll(SELECTOR).forEach(observe);
  };

  scan();
  new MutationObserver(scan).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
