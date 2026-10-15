"use strict";

// The page never builds HTML from data: every dynamic value goes in through textContent.
(function () {
  const token = document.querySelector('meta[name="studio-token"]').content;
  const $ = (id) => document.getElementById(id);
  const state = { models: [], plan: null, approval: null, run: null, expiryTimer: null };

  async function call(method, path, body) {
    const options = { method: method, headers: { Accept: "application/json" }, cache: "no-store" };
    if (method === "POST") {
      options.headers["Content-Type"] = "application/json";
      options.headers["X-Studio-Token"] = token;
      options.body = JSON.stringify(body || {});
    }
    const response = await fetch(path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.message || "HTTP " + response.status);
      error.code = data.error || "http_" + response.status;
      throw error;
    }
    return data;
  }

  // One action at a time: a second click while a request is in flight is ignored.
  let busy = false;
  function guarded(task, element) {
    return async () => {
      if (busy) return;
      busy = true;
      try {
        await task();
      } catch (error) {
        element.textContent = (error.code || "error") + ": " + error.message;
      } finally {
        busy = false;
        refreshButtons();
      }
    };
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
      reader.onerror = () => reject(new Error("could not read " + file.name));
      reader.readAsDataURL(file);
    });
  }

  // A size with no official price shows no estimate; the page never prints a number it did not read from the catalog.
  function sizeLabel(model, size) {
    const price = model.prices_usd_per_image[size];
    if (price === undefined) return size + " (cost not verified in an official page: no estimate)";
    return size + " (US$ " + price + " per image, nominal)";
  }

  function fillSizes() {
    const model = state.models.find((m) => m.id === $("model").value);
    const select = $("size");
    const previous = select.value;
    select.replaceChildren();
    for (const size of model ? model.sizes : []) {
      const option = document.createElement("option");
      option.value = size;
      option.textContent = sizeLabel(model, size);
      select.appendChild(option);
    }
    if (model && model.sizes.includes(previous)) select.value = previous;
  }

  function renderModels(data) {
    state.models = data.models;
    const select = $("model");
    const previous = select.value;
    select.replaceChildren();
    for (const model of data.models) {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.name + " (" + model.id + ", " + model.provider + ")";
      select.appendChild(option);
    }
    if (data.models.some((m) => m.id === previous)) select.value = previous;
    fillSizes();
  }

  function fillAspects() {
    const select = $("aspect");
    const model = state.models.find((m) => m.id === $("model").value);
    const ratios = model ? model.aspect_ratios : [];
    const previous = select.value;
    select.replaceChildren();
    for (const ratio of ratios) {
      const option = document.createElement("option");
      option.value = ratio;
      option.textContent = ratio;
      select.appendChild(option);
    }
    if (ratios.includes(previous)) select.value = previous;
    else if (ratios.includes("1:1")) select.value = "1:1";
  }

  function renderHistory(data) {
    const body = $("runs");
    body.replaceChildren();
    for (const run of data.runs) {
      const row = document.createElement("tr");
      const cells = [run.started_at, run.model, run.image_size, run.aspect_ratio, run.status,
        run.verdict || "-", run.rating === null ? "-" : run.rating];
      for (const text of cells) {
        const cell = document.createElement("td");
        cell.textContent = String(text);
        row.appendChild(cell);
      }
      body.appendChild(row);
    }
    const list = $("preferences");
    list.replaceChildren();
    for (const key of ["model", "aspect_ratio"]) {
      for (const [label, value] of Object.entries(data.preferences[key])) {
        const item = document.createElement("li");
        item.textContent = key + " " + label + ": average " + value.average + " over " + value.count + " rated run(s)";
        list.appendChild(item);
      }
    }
    if (!list.children.length) {
      const item = document.createElement("li");
      item.textContent = "No ratings yet.";
      list.appendChild(item);
    }
  }

  async function loadState() {
    const data = await call("GET", "/api/state");
    renderModels(data);
    fillAspects();
    renderHistory(data);
    $("provider-status").textContent = data.provider === "fake"
      ? "Fake provider: placeholder images, no network, no cost."
      : "Live providers. " + data.providers.map((p) => p.name + (p.configured ? ": key set"
        : ": not set (" + p.env.join(", ") + ")")).join("; ") + ".";
    refreshButtons();
  }

  function addRow(list, term, text) {
    const dt = document.createElement("dt");
    dt.textContent = term;
    const dd = document.createElement("dd");
    dd.textContent = text;
    list.append(dt, dd);
  }

  function showPlan(plan) {
    const list = $("plan");
    list.replaceChildren();
    addRow(list, "Prompt", plan.brief.prompt);
    addRow(list, "Model", plan.brief.model);
    addRow(list, "Image size", plan.brief.image_size);
    addRow(list, "Aspect ratio", plan.brief.aspect_ratio);
    addRow(list, "Reference images", String(plan.brief.references.length));
    addRow(list, "Estimated cost", plan.estimated_cost_usd === null
      ? "not verified in an official page: no estimate. The approval is still needed for this run."
      : "US$ " + plan.estimated_cost_usd + " for one image at the standard price (nominal; no batch discount)");
    addRow(list, "Brief hash", plan.brief_sha256);
    const warnings = $("plan-warnings");
    warnings.replaceChildren();
    for (const finding of plan.warnings) {
      const item = document.createElement("li");
      item.textContent = finding.level + " " + finding.code + ": " + finding.message;
      warnings.appendChild(item);
    }
  }

  function dropApproval() {
    clearTimeout(state.expiryTimer);
    state.approval = null;
    $("approval-status").textContent = state.plan
      ? "Approve the plan to run it once."
      : "No approval. Build a plan first.";
  }

  // The approval is bound to the brief's hash, so any edit means a new plan and a new approval.
  function invalidatePlan() {
    if (!state.plan) return;
    state.plan = null;
    dropApproval();
    $("plan").replaceChildren();
    $("plan-warnings").replaceChildren();
    $("brief-message").textContent = "The brief changed. Build the plan again before approving.";
    refreshButtons();
  }

  async function buildPlan() {
    $("brief-message").textContent = "Checking the brief...";
    const references = [];
    for (const file of $("references").files) {
      const data = await fileToBase64(file);
      references.push(await call("POST", "/api/inputs", { mime_type: file.type, data: data }));
    }
    const plan = await call("POST", "/api/briefs", {
      prompt: $("prompt").value,
      model: $("model").value,
      aspect_ratio: $("aspect").value,
      image_size: $("size").value,
      references: references,
    });
    state.plan = plan;
    state.run = null;
    dropApproval();
    showPlan(plan);
    $("brief-message").textContent = "Plan ready. Approve it once to unlock one paid run.";
    $("run-status").textContent = "";
    $("output").hidden = true;
    $("review-status").textContent = "";
    $("evaluation-status").textContent = "";
    refreshButtons();
  }

  function armExpiry() {
    clearTimeout(state.expiryTimer);
    if (!state.approval) return;
    state.expiryTimer = setTimeout(() => {
      state.approval = null;
      $("approval-status").textContent = "The approval expired. Approve the plan again.";
      refreshButtons();
    }, Math.max(0, state.approval.expiresAt - Date.now()));
  }

  async function approve() {
    const data = await call("POST", "/api/approvals", { brief_sha256: state.plan.brief_sha256 });
    state.approval = { id: data.approval_id, expiresAt: new Date(data.expires_at) };
    $("approval-status").textContent = "Approved for one run until " + state.approval.expiresAt.toLocaleTimeString()
      + ". The run spends this approval.";
    armExpiry();
    refreshButtons();
  }

  async function run() {
    // Cleared before the request, so the page can never send the same approval twice.
    const approvalId = state.approval.id;
    state.approval = null;
    clearTimeout(state.expiryTimer);
    $("approval-status").textContent = "Approval sent with this run.";
    $("run-status").textContent = "Running: one paid call is in progress.";
    refreshButtons();
    let record;
    try {
      record = await call("POST", "/api/runs", { brief_sha256: state.plan.brief_sha256, approval_id: approvalId });
    } catch (error) {
      $("approval-status").textContent = "The run did not start. Fix the problem, then approve the plan again.";
      throw error;
    }
    state.run = record;
    const image = $("output");
    if (record.status === "generated") {
      image.src = "/api/runs/" + record.run_id + "/image";
      image.hidden = false;
      $("run-status").textContent = "Generated " + record.run_id + ". Review it below.";
    } else {
      image.hidden = true;
      image.removeAttribute("src");
      $("run-status").textContent = "Failed (" + record.error + "): " + record.error_message;
    }
    $("approval-status").textContent = "Approval spent. Approve again to run this brief once more.";
    $("review-status").textContent = "";
    $("evaluation-status").textContent = "";
    await loadState();
  }

  async function review(verdict) {
    state.run = await call("POST", "/api/runs/" + state.run.run_id + "/review",
      { verdict: verdict, note: $("review-note").value });
    $("review-status").textContent = "Saved verdict: " + verdict + ".";
    await loadState();
  }

  async function evaluate() {
    state.run = await call("POST", "/api/runs/" + state.run.run_id + "/evaluation",
      { rating: Number($("rating").value), note: $("evaluation-note").value });
    $("evaluation-status").textContent = "Saved rating " + state.run.rating + ".";
    await loadState();
  }

  function refreshButtons() {
    const hasPlan = state.plan !== null;
    $("approve-button").disabled = !hasPlan;
    $("run-button").disabled = !(hasPlan && state.approval !== null);
    const generated = state.run !== null && state.run.status === "generated";
    for (const button of document.querySelectorAll("#verdicts button")) {
      button.disabled = !generated;
    }
    $("evaluate-button").disabled = !generated;
  }

  $("model").addEventListener("change", () => {
    fillSizes();
    fillAspects();
    invalidatePlan();
  });
  for (const id of ["prompt", "aspect", "size", "references"]) {
    $(id).addEventListener("input", invalidatePlan);
    $(id).addEventListener("change", invalidatePlan);
  }
  $("plan-button").addEventListener("click", guarded(buildPlan, $("brief-message")));
  $("approve-button").addEventListener("click", guarded(approve, $("approval-status")));
  $("run-button").addEventListener("click", guarded(run, $("run-status")));
  for (const button of document.querySelectorAll("#verdicts button")) {
    button.addEventListener("click", guarded(() => review(button.dataset.verdict), $("review-status")));
  }
  $("evaluate-button").addEventListener("click", guarded(evaluate, $("evaluation-status")));
  guarded(loadState, $("provider-status"))();
  refreshButtons();
})();
