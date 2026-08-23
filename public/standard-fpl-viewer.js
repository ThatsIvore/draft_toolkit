"use strict";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const FORBIDDEN_KEYS = new Set([
  "entry_id",
  "owner_entry_id",
  "owner_raw",
  "access_token",
  "refresh_token",
  "id_token",
  "authorization",
  "password",
  "cookie",
]);

const fileInput = document.querySelector("#report-file");
const dropZone = document.querySelector("#drop-zone");
const statusNode = document.querySelector("#loader-status");
const dashboard = document.querySelector("#dashboard");
const clearButton = document.querySelector("#clear-report");

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function setStatus(message, kind = "") {
  statusNode.textContent = message;
  statusNode.className = `status${kind ? ` ${kind}` : ""}`;
}

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function displayMoney(value) {
  return value === null || value === undefined ? "Unavailable" : `£${number(value).toFixed(1)}m`;
}

function scanKeys(value, path = "report") {
  if (Array.isArray(value)) {
    value.forEach((item, index) => scanKeys(item, `${path}[${index}]`));
    return;
  }
  if (!value || typeof value !== "object") return;
  Object.entries(value).forEach(([key, child]) => {
    if (FORBIDDEN_KEYS.has(key.toLowerCase())) {
      throw new Error(`Private report contains forbidden field ${path}.${key}.`);
    }
    scanKeys(child, `${path}.${key}`);
  });
}

function validateReport(report) {
  if (!report || typeof report !== "object" || Array.isArray(report)) {
    throw new Error("The selected file is not a JSON report object.");
  }
  scanKeys(report);
  if (report.mode !== "standard_fpl") {
    throw new Error("This viewer accepts only private Standard FPL reports.");
  }
  if (!/^phase-[1-9]\d*-v\d+\.\d+$/.test(String(report.poc_version || ""))) {
    throw new Error("The report has an unsupported or missing POC version.");
  }
  if (!Number.isInteger(report.decision_gameweek) || report.decision_gameweek < 1 || report.decision_gameweek > 38) {
    throw new Error("The report has an invalid decision Gameweek.");
  }
  if (!Array.isArray(report.planning_gameweeks) || !report.planning_gameweeks.length) {
    throw new Error("The report has no actionable planning Gameweeks.");
  }
  if (!report.recommended_lineup || !Array.isArray(report.recommended_lineup.starters)) {
    throw new Error("The report has no Recommended XI.");
  }
  if (!report.squad_outlook || !Array.isArray(report.squad_outlook.rounds)) {
    throw new Error("The report predates the four-Gameweek squad outlook.");
  }
  if (!report.transfer_decision || typeof report.transfer_decision !== "object") {
    throw new Error("The report has no hold-versus-transfer decision.");
  }
  return report;
}

function playerChip(player, includeScore = true) {
  const chip = element("span", "player-chip");
  chip.append(element("span", "", player.player || `Player ${player.player_id || "?"}`));
  const details = [];
  if (player.position) details.push(player.position);
  const score = player.start_score ?? (player.selection || {}).start_score;
  if (includeScore && score !== undefined && score !== null) details.push(`Start ${number(score).toFixed(1)}`);
  if (details.length) chip.append(element("small", "", details.join(" · ")));
  return chip;
}

function appendPlayerList(container, players, emptyText = "None") {
  container.replaceChildren();
  if (!players || !players.length) {
    container.append(element("span", "muted", emptyText));
    return;
  }
  players.forEach((player) => container.append(playerChip(player)));
}

function renderStats(report) {
  const container = document.querySelector("#summary-stats");
  const finance = report.financial_snapshot || {};
  const stats = [
    ["Bank", displayMoney(finance.bank)],
    ["Squad value", displayMoney(finance.squad_value)],
    ["Free transfers", finance.free_transfers ?? "Unavailable"],
    ["Planning rounds", (report.planning_gameweeks || []).length],
  ];
  container.replaceChildren(...stats.map(([label, value]) => {
    const card = element("div", "stat");
    card.append(element("small", "", label), element("strong", "", value));
    return card;
  }));
}

function renderDecision(report) {
  const decision = report.transfer_decision || {};
  const recommendation = String(decision.recommendation || "UNAVAILABLE").toUpperCase();
  const badge = document.querySelector("#decision-badge");
  badge.textContent = recommendation;
  badge.className = `decision-badge ${recommendation.toLowerCase()}`;
  document.querySelector("#decision-summary").textContent = decision.summary || "No decision summary is available.";

  const candidateNode = document.querySelector("#decision-candidate");
  candidateNode.replaceChildren();
  const candidate = decision.candidate;
  if (candidate && candidate.outgoing && candidate.incoming) {
    const card = element("div", "move-card");
    card.append(
      playerChip(candidate.outgoing, false),
      element("span", "move-arrow", "→"),
      playerChip(candidate.incoming, false),
      element("span", "soft-pill", `${candidate.action || "REVIEW"} · ${candidate.confidence || "?"} · Δ ${number((candidate.heuristic || {}).score).toFixed(1)}`),
    );
    candidateNode.append(card);
  }

  const reasons = document.querySelector("#decision-reasons");
  reasons.replaceChildren();
  (decision.reasons || []).forEach((reason) => reasons.append(element("li", "", reason.message || reason.code)));
  if (!reasons.childElementCount) reasons.append(element("li", "muted", "No additional reason was supplied."));
}

function renderLineup(report) {
  const lineup = report.recommended_lineup || {};
  document.querySelector("#formation-pill").textContent = lineup.formation || "No legal formation";
  const captaincy = report.captaincy || {};
  const captainNode = document.querySelector("#captaincy");
  captainNode.replaceChildren();
  [["Captain", captaincy.captain], ["Vice-captain", captaincy.vice_captain]].forEach(([label, player]) => {
    const card = element("div", "captain-card");
    card.append(element("small", "", label));
    card.append(element("strong", "", player ? player.player : "Unavailable"));
    if (player) card.append(element("span", "muted", `Captain Score ${number(player.captain_score).toFixed(1)}`));
    captainNode.append(card);
  });

  const groupsNode = document.querySelector("#lineup-groups");
  groupsNode.replaceChildren();
  ["GKP", "DEF", "MID", "FWD"].forEach((position) => {
    const group = element("div", "position-group");
    group.append(element("h3", "", position));
    const row = element("div", "player-row");
    appendPlayerList(row, (lineup.starters || []).filter((player) => player.position === position));
    group.append(row);
    groupsNode.append(group);
  });

  const bench = [...(lineup.bench || [])];
  if (lineup.reserve_goalkeeper) bench.push(lineup.reserve_goalkeeper);
  appendPlayerList(document.querySelector("#bench-row"), bench, "No bench was generated.");
}

function compactNames(players) {
  return (players || []).map((player) => player.player || `Player ${player.player_id || "?"}`);
}

function renderOutlook(report) {
  const outlook = report.squad_outlook || {};
  const grid = document.querySelector("#outlook-grid");
  grid.replaceChildren();
  (outlook.rounds || []).forEach((round) => {
    const card = element("article", "gw-card");
    const head = element("div", "gw-card-head");
    head.append(element("strong", "", `GW${round.gameweek} · ${round.formation || "—"}`));
    const pressure = String(round.selection_pressure || "UNKNOWN").toLowerCase();
    head.append(element("span", `pressure ${pressure}`, pressure.toUpperCase()));
    const body = element("div", "gw-card-body");
    body.append(
      element("p", "", `Captain: ${(round.captain || {}).player || "Unavailable"}`),
      element("p", "", `Vice: ${(round.vice_captain || {}).player || "Unavailable"}`),
      element("p", "", `Start Score total: ${round.total_start_score ?? "—"}`),
      element("p", "", `Playable bench: ${round.playable_outfield_bench_count ?? "—"}`),
    );
    const list = element("ul", "mini-list");
    compactNames(round.availability_risks).forEach((name) => list.append(element("li", "", `${name} · availability/minutes review`)));
    if (!list.childElementCount) list.append(element("li", "", "No starter availability flags"));
    body.append(list);
    card.append(head, body);
    grid.append(card);
  });

  const usage = document.querySelector("#usage-grid");
  usage.replaceChildren();
  [
    ["Core starters", outlook.core_starters],
    ["Rotation players", outlook.rotation_players],
    ["Always benched", outlook.always_benched],
  ].forEach(([label, players]) => {
    const card = element("div", "usage-card");
    card.append(element("h3", "", label));
    const row = element("div", "player-row");
    appendPlayerList(row, players, "None");
    card.append(row);
    usage.append(card);
  });
}

function renderCandidates(report) {
  const container = document.querySelector("#transfer-candidates");
  const candidates = ((report.single_transfer_candidates || {}).candidates || []).slice(0, 5);
  container.replaceChildren();
  if (!candidates.length) {
    container.append(element("p", "muted", (report.single_transfer_candidates || {}).reason || "No legal single-transfer candidates are available."));
    return;
  }
  candidates.forEach((candidate) => {
    const card = element("article", "candidate-card");
    card.append(
      playerChip(candidate.outgoing || {}, false),
      element("span", "move-arrow", "→"),
      playerChip(candidate.incoming || {}, false),
      element("span", "candidate-meta soft-pill", `${candidate.action || "REVIEW"} · Δ ${number((candidate.heuristic || {}).score).toFixed(1)} · ${(candidate.confidence || "?")}`),
    );
    container.append(card);
  });
}

function renderOutcomes(report) {
  const container = document.querySelector("#outcome-content");
  const outcomes = report.transfer_outcomes || {};
  const rows = [...(outcomes.history || [])];
  if (outcomes.current) rows.push(outcomes.current);
  container.replaceChildren();
  if (!rows.length) {
    container.append(element("p", "muted", "No frozen transfer decision has been captured yet."));
    return;
  }
  rows.slice(-5).reverse().forEach((row) => {
    const forecast = row.forecast || {};
    const evaluation = row.evaluation || {};
    const card = element("div", "outcome-row");
    const result = evaluation.complete ? evaluation.comparison_result : "Tracking";
    card.append(
      element("strong", "", `GW${forecast.gameweek || row.gameweek || "?"} · ${forecast.recommendation || "Decision"} · ${result || "Complete"}`),
      element("p", "muted", forecast.summary || evaluation.reason || "Waiting for matching Gameweek results."),
    );
    container.append(card);
  });
}

function renderReport(report) {
  document.querySelector("#team-name").textContent = (report.entry_context || {}).team_name || "Private team";
  const generated = report.generated_at ? new Date(report.generated_at) : null;
  document.querySelector("#report-meta").textContent = `${report.poc_version} · Generated ${generated && !Number.isNaN(generated.valueOf()) ? generated.toLocaleString() : "at an unknown time"}`;
  document.querySelector("#gw-pill").textContent = `Live GW${report.current_gameweek ?? "—"} · Plan GW${report.decision_gameweek}`;
  renderStats(report);
  renderDecision(report);
  renderLineup(report);
  renderOutlook(report);
  renderCandidates(report);
  renderOutcomes(report);
  dashboard.hidden = false;
  setStatus("Private report loaded in this tab only.", "good");
  dashboard.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function readReportFile(file) {
  if (!file) return;
  if (file.size > MAX_FILE_BYTES) throw new Error("The selected report is larger than 5 MB.");
  const source = await file.text();
  let parsed;
  try {
    parsed = JSON.parse(source);
  } catch (_error) {
    throw new Error("The selected file is not valid JSON.");
  }
  renderReport(validateReport(parsed));
}

async function handleFile(file) {
  try {
    setStatus("Validating private report…");
    await readReportFile(file);
  } catch (error) {
    dashboard.hidden = true;
    setStatus(error instanceof Error ? error.message : "The private report could not be loaded.", "error");
  }
}

function clearReport() {
  dashboard.hidden = true;
  [
    "#team-name",
    "#report-meta",
    "#gw-pill",
    "#summary-stats",
    "#decision-badge",
    "#decision-summary",
    "#decision-candidate",
    "#decision-reasons",
    "#formation-pill",
    "#captaincy",
    "#lineup-groups",
    "#bench-row",
    "#outlook-grid",
    "#usage-grid",
    "#transfer-candidates",
    "#outcome-content",
  ].forEach((selector) => document.querySelector(selector).replaceChildren());
  if (fileInput) fileInput.value = "";
  setStatus("Private report cleared from this tab.");
  document.querySelector("#loader-card").scrollIntoView({ behavior: "smooth", block: "start" });
}

window.standardFplReportViewer = Object.freeze({ validateReport, renderReport, clearReport, setStatus });

if (fileInput && dropZone) {
  fileInput.addEventListener("change", () => handleFile(fileInput.files && fileInput.files[0]));
  ["dragenter", "dragover"].forEach((type) => dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  }));
  ["dragleave", "drop"].forEach((type) => dropZone.addEventListener(type, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  }));
  dropZone.addEventListener("drop", (event) => handleFile(event.dataTransfer && event.dataTransfer.files[0]));
}
if (clearButton) clearButton.addEventListener("click", clearReport);
