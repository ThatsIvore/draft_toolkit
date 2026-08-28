"use strict";

const snapshotForm = document.querySelector("#snapshot-form");
const snapshotInput = document.querySelector("#snapshot-file");
const entryUrlInput = document.querySelector("#entry-url");
const submitButton = document.querySelector("#generate-report");
const MAX_SNAPSHOT_BYTES = 256 * 1024;

async function generatePrivateReport(event) {
  event.preventDefault();
  const viewer = window.standardFplReportViewer;
  const file = snapshotInput.files && snapshotInput.files[0];
  if (!file) {
    viewer.setStatus("Choose your sanitized Standard FPL snapshot first.", "error");
    return;
  }
  if (file.size > MAX_SNAPSHOT_BYTES) {
    viewer.setStatus("The snapshot is larger than the 256 KB runner limit.", "error");
    return;
  }
  const entryUrl = entryUrlInput.value.trim();
  if (!/^https:\/\/fantasy\.premierleague\.com\/(?:en\/)?entry\/[1-9]\d*(?:\/|$)/.test(entryUrl)) {
    viewer.setStatus("Paste an ordinary fantasy.premierleague.com entry URL.", "error");
    return;
  }

  const body = new FormData();
  body.append("entry_url", entryUrl);
  body.append("snapshot", file, file.name || "standard-fpl-current-team.json");
  submitButton.disabled = true;
  viewer.setStatus("Validating the snapshot and fetching public FPL data…");
  try {
    const response = await fetch("/api/standard-fpl/report", {
      method: "POST",
      body,
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload && payload.message ? payload.message : "The private report could not be generated.");
    }
    viewer.renderReport(viewer.validateReport(payload));
  } catch (error) {
    document.querySelector("#dashboard").hidden = true;
    viewer.setStatus(error instanceof Error ? error.message : "The private report could not be generated.", "error");
  } finally {
    submitButton.disabled = false;
  }
}

snapshotForm.addEventListener("submit", generatePrivateReport);
document.querySelector("#clear-report").addEventListener("click", () => {
  snapshotInput.value = "";
});
