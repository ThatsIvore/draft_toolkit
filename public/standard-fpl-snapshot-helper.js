(async () => {
  "use strict";

  const installLink = document.getElementById("bookmarklet-link");
  const status = document.getElementById("installer-status");
  try {
    const response = await fetch("standard-fpl-snapshot-bookmarklet.js", {
      credentials: "omit",
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const source = (await response.text()).trim();
    if (!source.startsWith("(async () =>")) throw new Error("unexpected helper source");
    installLink.href = `javascript:${source}`;
    installLink.classList.remove("disabled");
    installLink.setAttribute("aria-disabled", "false");
    status.textContent = "Ready to drag to your bookmarks bar.";
  } catch (error) {
    installLink.removeAttribute("href");
    status.textContent = `Installer could not load: ${error instanceof Error ? error.message : String(error)}.`;
    status.classList.add("error-text");
  }

  installLink.addEventListener("click", (event) => {
    event.preventDefault();
    status.textContent = "Drag this button to the bookmarks bar; clicking it on this page does not install it.";
  });
})();
