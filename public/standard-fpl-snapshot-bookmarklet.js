(async () => {
  "use strict";

  const FPL_ORIGIN = "https://fantasy.premierleague.com";
  const STAGE_KEY = "draft_toolkit_standard_fpl_snapshot_v1";
  const SNAPSHOT_VERSION = "standard-fpl-private-snapshot-v1";
  const CHIP_DEFINITIONS = [
    ["Bench Boost", "bench_boost"],
    ["Triple Captain", "triple_captain"],
    ["Wildcard", "wildcard"],
    ["Free Hit", "freehit"],
  ];

  const fail = (message) => {
    throw new Error(message);
  };

  const normalizedText = (value) =>
    String(value || "")
      .replace(/\s+/g, " ")
      .trim();

  const normalizedKey = (value) => normalizedText(value).toLocaleLowerCase("en-GB");

  const integer = (value, label, minimum, maximum) => {
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
      fail(`${label} must be an integer between ${minimum} and ${maximum}.`);
    }
    return value;
  };

  const moneyTenths = (value, label, minimum = 0) => {
    const match = normalizedText(value).match(/£?\s*(\d+(?:\.\d)?)\s*m?/i);
    if (!match) fail(`Could not read ${label}.`);
    const tenths = Math.round(Number(match[1]) * 10);
    return integer(tenths, label, minimum, 2000);
  };

  const pageGameweek = () => {
    const headings = [...document.querySelectorAll("h1, h2, h3")]
      .map((node) => normalizedText(node.textContent));
    for (const heading of headings) {
      const match = heading.match(/Gameweek\s+(\d{1,2})/i);
      if (match) return integer(Number(match[1]), "decision_gameweek", 1, 38);
    }
    fail("Could not identify the decision Gameweek from the page heading.");
  };

  const matchingButton = (label) =>
    [...document.querySelectorAll("button")].find((button) =>
      normalizedKey(button.textContent).includes(normalizedKey(label))
    );

  const isEnabled = (button) =>
    Boolean(button) && !button.disabled && button.getAttribute("aria-disabled") !== "true";

  const assertNoPendingChanges = (label) => {
    const button = matchingButton(label);
    if (isEnabled(button)) {
      fail(`Pending team changes were detected. Cancel or save them before using the helper; it will not press ${label}.`);
    }
  };

  const chipControlText = (label) => {
    const labelKey = normalizedKey(label);
    const directButton = [...document.querySelectorAll("button")].find((button) => {
      const accessible = [button.textContent, button.getAttribute("aria-label"), button.title]
        .map(normalizedKey)
        .join(" ");
      return accessible.includes(labelKey);
    });
    if (directButton) {
      return normalizedText([
        directButton.textContent,
        directButton.getAttribute("aria-label"),
        directButton.title,
      ].join(" "));
    }

    const labelNode = [...document.querySelectorAll("h1, h2, h3, h4, h5, h6, span, p")]
      .filter((node) => normalizedKey(node.textContent) === labelKey)
      .sort((left, right) => left.textContent.length - right.textContent.length)[0];
    if (!labelNode) fail(`Could not find the ${label} chip control.`);

    let container = labelNode.parentElement;
    for (let depth = 0; container && depth < 6; depth += 1, container = container.parentElement) {
      const buttons = [...container.querySelectorAll("button")];
      if (buttons.length) {
        return normalizedText(`${container.textContent} ${buttons.map((button) => button.getAttribute("aria-label") || "").join(" ")}`);
      }
    }
    fail(`Could not read the ${label} chip state.`);
  };

  const captureChips = (decisionGameweek) => {
    const number = decisionGameweek <= 19 ? 1 : 2;
    return CHIP_DEFINITIONS.map(([label, name]) => {
      const controlText = chipControlText(label);
      const stateText = normalizedKey(controlText)
        .split(normalizedKey(label))
        .join(" ");
      let status;
      let playedGameweek = null;
      if (/\bactive\b/.test(stateText)) {
        status = "active";
      } else if (/\bplayed\b|\bused\b/.test(stateText)) {
        const playedMatch = controlText.match(/(?:Gameweek|GW)\s*(\d{1,2})/i);
        if (!playedMatch) fail(`The ${label} chip looks played, but its Gameweek is not visible.`);
        status = "played";
        playedGameweek = integer(Number(playedMatch[1]), `${label} played_gameweek`, 1, 38);
      } else if (/\bunavailable\b|\blocked\b/.test(stateText)) {
        status = "unavailable";
      } else if (/\bplay\b|\bavailable\b/.test(stateText)) {
        status = "available";
      } else {
        fail(`Could not safely classify the ${label} chip state.`);
      }
      return { name, number, status, played_gameweek: playedGameweek };
    });
  };

  const bootstrapData = async () => {
    const response = await fetch(`${FPL_ORIGIN}/api/bootstrap-static/`, {
      credentials: "omit",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) fail(`The public player list returned HTTP ${response.status}.`);
    const payload = await response.json();
    if (!Array.isArray(payload.elements) || !Array.isArray(payload.teams) || !Array.isArray(payload.element_types)) {
      fail("The public player list has an unexpected shape.");
    }
    return payload;
  };

  const capturePickTeam = async () => {
    assertNoPendingChanges("Save Team");
    const table = document.querySelector('table[aria-label="Pick Team List"]');
    if (!table) fail("Select List view on Pick Team, then run the helper again.");

    const headers = [...table.querySelectorAll("thead th")].map((node) => normalizedText(node.textContent));
    for (const required of ["CP", "PP", "SP"]) {
      if (!headers.includes(required)) {
        fail("Select Selling Price in the Pick Team display options, then run the helper again.");
      }
    }

    const decisionGameweek = pageGameweek();
    const chips = captureChips(decisionGameweek);
    const rows = [...table.querySelectorAll("tbody tr")]
      .filter((row) => row.querySelectorAll("td").length >= 3);
    if (rows.length !== 15) fail(`Expected 15 Pick Team rows, found ${rows.length}.`);

    const visiblePicks = rows.map((row, index) => {
      const identity = normalizedText(row.querySelector("th span")?.textContent);
      const separator = identity.lastIndexOf(",");
      if (separator < 1) fail(`Could not read the player and club in row ${index + 1}.`);
      const name = normalizedText(identity.slice(0, separator));
      const club = normalizedText(identity.slice(separator + 1));
      const position = [...row.querySelectorAll("th span")]
        .map((span) => normalizedText(span.textContent))
        .find((value) => /^(GKP|DEF|MID|FWD)$/.test(value));
      if (!position) fail(`Could not read the position in row ${index + 1}.`);
      const cells = [...row.querySelectorAll("td")];
      if (cells.length < 3) fail(`Could not read all prices in row ${index + 1}.`);
      return {
        name,
        club,
        position,
        lineup_position: index + 1,
        is_captain: Boolean(row.querySelector('[aria-label="Captain"]')),
        is_vice_captain: Boolean(row.querySelector('[aria-label="Vice Captain"], [aria-label="Vice-Captain"]')),
        purchase_price_tenths: moneyTenths(cells[1].textContent, `row ${index + 1} purchase price`, 1),
        selling_price_tenths: moneyTenths(cells[2].textContent, `row ${index + 1} selling price`, 1),
      };
    });

    const expectedShape = { GKP: 2, DEF: 5, MID: 5, FWD: 3 };
    for (const [position, expected] of Object.entries(expectedShape)) {
      const actual = visiblePicks.filter((pick) => pick.position === position).length;
      if (actual !== expected) fail(`Expected ${expected} ${position} players, found ${actual}.`);
    }
    if (visiblePicks.filter((pick) => pick.is_captain).length !== 1) fail("Expected exactly one captain.");
    if (visiblePicks.filter((pick) => pick.is_vice_captain).length !== 1) fail("Expected exactly one vice-captain.");
    if (visiblePicks.some((pick) => (pick.is_captain || pick.is_vice_captain) && pick.lineup_position > 11)) {
      fail("Captain and vice-captain must both be starters.");
    }

    const bootstrap = await bootstrapData();
    const teamById = new Map(bootstrap.teams.map((team) => [team.id, team]));
    const positionById = new Map(bootstrap.element_types.map((position) => [position.id, position.singular_name_short]));
    const squad = visiblePicks.map((pick) => {
      const matches = bootstrap.elements.filter((player) => {
        const team = teamById.get(player.team);
        return normalizedKey(player.web_name) === normalizedKey(pick.name)
          && [team?.name, team?.short_name].map(normalizedKey).includes(normalizedKey(pick.club))
          && normalizedKey(positionById.get(player.element_type)) === normalizedKey(pick.position);
      });
      if (matches.length !== 1) {
        fail(`Could not uniquely map ${pick.name} (${pick.club}, ${pick.position}) to the public player list.`);
      }
      return {
        player_id: integer(matches[0].id, "player_id", 1, 1000000),
        lineup_position: pick.lineup_position,
        is_captain: pick.is_captain,
        is_vice_captain: pick.is_vice_captain,
        purchase_price_tenths: pick.purchase_price_tenths,
        selling_price_tenths: pick.selling_price_tenths,
      };
    });
    if (new Set(squad.map((pick) => pick.player_id)).size !== 15) fail("Mapped player IDs are not unique.");

    const partial = { decision_gameweek: decisionGameweek, squad, chips };
    sessionStorage.setItem(STAGE_KEY, JSON.stringify(partial));
    alert("Pick Team captured safely. The helper will open Transfers; click the same bookmark once more there.");
    location.assign("/en/transfers");
  };

  const labelledValue = (root, label) => {
    const labelKey = normalizedKey(label);
    const candidates = [...root.querySelectorAll('[role="status"], h3, h4')]
      .filter((node) => normalizedKey(node.textContent).startsWith(labelKey));
    for (const candidate of candidates) {
      let container = candidate;
      for (let depth = 0; container && depth < 4; depth += 1, container = container.parentElement) {
        const text = normalizedText(container.textContent);
        if (normalizedKey(text).startsWith(labelKey) && text.length > label.length) {
          return normalizedText(text.slice(label.length));
        }
      }
    }
    fail(`Could not find ${label} on Transfers.`);
  };

  const visibleTransferHistorySummary = async () => {
    const visibleEntryUrls = [...document.querySelectorAll('a[href*="/entry/"]')]
      .map((link) => new URL(link.href, location.href))
      .filter((url) => url.origin === FPL_ORIGIN);
    let historyUrl = visibleEntryUrls
      .find((url) => /^\/en\/entry\/\d+\/transfers\/?$/.test(url.pathname));
    if (!historyUrl) {
      const entryEventUrl = visibleEntryUrls
        .find((url) => /^\/en\/entry\/\d+\/event\/\d+\/?$/.test(url.pathname));
      const entryMatch = entryEventUrl?.pathname.match(/^\/en\/entry\/(\d+)\//);
      if (entryMatch) historyUrl = new URL(`/en/entry/${entryMatch[1]}/transfers`, FPL_ORIGIN);
    }
    if (!historyUrl) fail("Could not find the signed-in entry's visible Transfer History link.");

    const popup = window.open(historyUrl.href, "draft_toolkit_fpl_history", "popup,width=720,height=820");
    if (!popup) fail("The browser blocked the read-only Transfer History window. Allow this popup and try again.");
    try {
      const deadline = Date.now() + 15000;
      while (Date.now() < deadline) {
        if (popup.closed) fail("The Transfer History window was closed before capture finished.");
        try {
          const bodyText = normalizedKey(popup.document?.body?.textContent);
          if (bodyText.includes("gameweek transfers") && bodyText.includes("squad value") && bodyText.includes("in the bank")) {
            return {
              transfers_made: labelledValue(popup.document, "Gameweek transfers"),
              squad_value: labelledValue(popup.document, "Squad value"),
              bank: labelledValue(popup.document, "In the bank"),
            };
          }
        } catch {
          // Same-origin navigation can briefly make the document unavailable while it loads.
        }
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
      fail("Transfer History did not finish loading within 15 seconds.");
    } finally {
      if (!popup.closed) popup.close();
    }
  };

  const exactKeys = (value, keys, label) => {
    const actual = Object.keys(value).sort();
    const expected = [...keys].sort();
    if (JSON.stringify(actual) !== JSON.stringify(expected)) fail(`${label} contains unexpected fields.`);
  };

  const validateSnapshot = (snapshot) => {
    exactKeys(snapshot, ["schema_version", "captured_at", "decision_gameweek", "squad", "transfers", "chips"], "snapshot");
    if (snapshot.schema_version !== SNAPSHOT_VERSION) fail("Unexpected snapshot schema version.");
    integer(snapshot.decision_gameweek, "decision_gameweek", 1, 38);
    if (!Array.isArray(snapshot.squad) || snapshot.squad.length !== 15) fail("Snapshot squad must contain 15 players.");
    const pickKeys = ["player_id", "lineup_position", "multiplier", "is_captain", "is_vice_captain", "purchase_price_tenths", "selling_price_tenths"];
    snapshot.squad.forEach((pick, index) => {
      exactKeys(pick, pickKeys, `squad[${index}]`);
      integer(pick.player_id, `squad[${index}].player_id`, 1, 1000000);
      integer(pick.lineup_position, `squad[${index}].lineup_position`, 1, 15);
      integer(pick.multiplier, `squad[${index}].multiplier`, 0, 3);
      integer(pick.purchase_price_tenths, `squad[${index}].purchase_price_tenths`, 1, 500);
      integer(pick.selling_price_tenths, `squad[${index}].selling_price_tenths`, 1, 500);
      if (typeof pick.is_captain !== "boolean" || typeof pick.is_vice_captain !== "boolean") fail("Captain flags must be booleans.");
      if (pick.is_captain && pick.is_vice_captain) fail(`squad[${index}] cannot be both captain and vice-captain.`);
      if ((pick.is_captain || pick.is_vice_captain) && pick.lineup_position > 11) fail(`squad[${index}] captaincy must belong to a starter.`);
      if (pick.is_captain && ![2, 3].includes(pick.multiplier)) fail(`squad[${index}] captain multiplier is invalid.`);
      if (!pick.is_captain && pick.multiplier !== (pick.lineup_position <= 11 ? 1 : 0)) fail(`squad[${index}] multiplier is invalid.`);
    });
    if (new Set(snapshot.squad.map((pick) => pick.player_id)).size !== 15) fail("Snapshot player IDs must be unique.");
    if (new Set(snapshot.squad.map((pick) => pick.lineup_position)).size !== 15) fail("Snapshot lineup positions must be unique.");
    if (snapshot.squad.filter((pick) => pick.is_captain).length !== 1) fail("Snapshot must contain one captain.");
    if (snapshot.squad.filter((pick) => pick.is_vice_captain).length !== 1) fail("Snapshot must contain one vice-captain.");

    exactKeys(snapshot.transfers, ["bank_tenths", "squad_value_tenths", "free_transfers", "transfers_made"], "transfers");
    integer(snapshot.transfers.bank_tenths, "transfers.bank_tenths", 0, 2000);
    integer(snapshot.transfers.squad_value_tenths, "transfers.squad_value_tenths", 1, 2000);
    integer(snapshot.transfers.free_transfers, "transfers.free_transfers", 0, 5);
    integer(snapshot.transfers.transfers_made, "transfers.transfers_made", 0, 100);

    if (!Array.isArray(snapshot.chips) || snapshot.chips.length !== 4) fail("Snapshot must contain four chip states.");
    snapshot.chips.forEach((chip, index) => {
      exactKeys(chip, ["name", "number", "status", "played_gameweek"], `chips[${index}]`);
      integer(chip.number, `chips[${index}].number`, 1, 2);
      if (!["available", "played", "active", "unavailable"].includes(chip.status)) fail(`chips[${index}] has an invalid status.`);
      if (chip.status === "played") integer(chip.played_gameweek, `chips[${index}].played_gameweek`, 1, 38);
      else if (chip.played_gameweek !== null) fail(`chips[${index}].played_gameweek must be null.`);
    });
    if (snapshot.chips.filter((chip) => chip.status === "active").length > 1) fail("Only one chip can be active.");
    return snapshot;
  };

  const captureTransfers = async () => {
    assertNoPendingChanges("Make Transfers");
    const partialRaw = sessionStorage.getItem(STAGE_KEY);
    if (!partialRaw) fail("No Pick Team capture was found. Start on Pick Team and run the helper there first.");
    let partial;
    try {
      partial = JSON.parse(partialRaw);
    } catch {
      fail("The staged capture is unreadable. Start again on Pick Team.");
    }
    exactKeys(partial, ["decision_gameweek", "squad", "chips"], "staged capture");
    const decisionGameweek = pageGameweek();
    if (partial.decision_gameweek !== decisionGameweek) fail("Pick Team and Transfers show different Gameweeks. Start again.");

    const freeTransfersText = labelledValue(document, "Free transfers");
    const freeTransfersMatch = freeTransfersText.match(/\b(\d+)\b/);
    if (!freeTransfersMatch) fail("Could not read free transfers.");
    const historySummary = await visibleTransferHistorySummary();
    const transfersMadeText = historySummary.transfers_made;
    const transfersMadeMatch = transfersMadeText.match(/\b(\d+)\b/);
    if (!transfersMadeMatch) fail("Could not read Gameweek transfers.");
    const bankTenths = moneyTenths(historySummary.bank, "bank", 0);
    const squadValueTenths = moneyTenths(historySummary.squad_value, "squad value", 1);

    const tripleCaptainActive = partial.chips.some((chip) => chip.name === "triple_captain" && chip.status === "active");
    const squad = partial.squad.map((pick) => ({
      player_id: pick.player_id,
      lineup_position: pick.lineup_position,
      multiplier: pick.lineup_position > 11 ? 0 : (pick.is_captain ? (tripleCaptainActive ? 3 : 2) : 1),
      is_captain: pick.is_captain,
      is_vice_captain: pick.is_vice_captain,
      purchase_price_tenths: pick.purchase_price_tenths,
      selling_price_tenths: pick.selling_price_tenths,
    }));
    const snapshot = validateSnapshot({
      schema_version: SNAPSHOT_VERSION,
      captured_at: new Date().toISOString(),
      decision_gameweek: decisionGameweek,
      squad,
      transfers: {
        bank_tenths: bankTenths,
        squad_value_tenths: squadValueTenths,
        free_transfers: integer(Number(freeTransfersMatch[1]), "free transfers", 0, 5),
        transfers_made: integer(Number(transfersMadeMatch[1]), "Gameweek transfers", 0, 100),
      },
      chips: partial.chips,
    });

    const blob = new Blob([`${JSON.stringify(snapshot, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "standard-fpl-current-team.json";
    link.hidden = true;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    alert("Private snapshot downloaded. Move it to data/private/current-team.json before running Standard FPL analysis.");
  };

  try {
    if (location.origin !== FPL_ORIGIN) fail("Run this bookmark only on fantasy.premierleague.com.");
    if (location.pathname === "/en/my-team" || location.pathname.startsWith("/en/my-team/")) {
      await capturePickTeam();
      return;
    }
    if (location.pathname === "/en/transfers" || location.pathname.startsWith("/en/transfers/")) {
      await captureTransfers();
      sessionStorage.removeItem(STAGE_KEY);
      return;
    }
    fail("Open Pick Team or Transfers on the official FPL site, then run this bookmark.");
  } catch (error) {
    sessionStorage.removeItem(STAGE_KEY);
    alert(`Standard FPL snapshot stopped safely: ${error instanceof Error ? error.message : String(error)}`);
  }
})();
