// Drives studio/static/app.js against the real local server (fake provider).
// The DOM is a small stub: enough for the page script, and nothing that pretends to be a browser.
// Counts are relative to the history the page starts with, so leftover runs in the data dir do not matter.
const base = process.env.STUDIO_BASE;
const realFetch = globalThis.fetch;
const failures = [];
const check = (ok, label) => {
  console.log((ok ? "PASS " : "FAIL ") + label);
  if (!ok) failures.push(label);
};

const page = await (await realFetch(base + "/")).text();
const token = /name="studio-token" content="([^"]+)"/.exec(page)[1];
const script = await (await realFetch(base + "/app.js")).text();

function element(tag = "div") {
  return {
    tagName: tag, children: [], dataset: {}, listeners: {}, hidden: false, disabled: false,
    textContent: "", src: undefined, files: [], _value: undefined,
    get options() { return this.children.filter((c) => c.tagName === "option"); },
    get value() {
      if (this._value !== undefined) return this._value;
      return this.options.length ? this.options[0].value : "";
    },
    set value(v) { this._value = v; },
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren() { this.children = []; },
    removeAttribute(name) { if (name === "src") this.src = undefined; },
    addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
  };
}

const byId = new Map();
const el = (id) => {
  if (!byId.has(id)) byId.set(id, element());
  return byId.get(id);
};
const meta = element("meta");
meta.content = token;
const verdicts = ["pass", "targeted_fix", "regenerate", "blocked"].map((v) => {
  const button = element("button");
  button.dataset.verdict = v;
  return button;
});
globalThis.document = {
  querySelector: (selector) => (selector.includes("studio-token") ? meta : null),
  getElementById: (id) => el(id),
  createElement: (tag) => element(tag),
  querySelectorAll: (selector) => (selector === "#verdicts button" ? verdicts : []),
};
globalThis.fetch = (path, options) => realFetch(base + path, options);

el("prompt").value = "Make a flat logo of a lighthouse.";
el("rating").value = "4";
(0, eval)(script);

const click = async (id) => { for (const fn of el(id).listeners.click || []) await fn({}); };
const clickVerdict = async (verdict) => {
  const button = verdicts.find((b) => b.dataset.verdict === verdict);
  for (const fn of button.listeners.click) await fn({});
};
// Wait until the page has finished its first state load: it sets the provider line last.
for (let i = 0; i < 200 && !el("provider-status").textContent; i++) {
  await new Promise((resolve) => setTimeout(resolve, 20));
}
const rowsAtStart = el("runs").children.length;

check(el("provider-status").textContent.startsWith("Fake provider"), "page reports the fake provider");
check(el("approve-button").disabled === true, "approve is off before a plan exists");
check(el("run-button").disabled === true, "run is off before approval");

await click("plan-button");
check(el("brief-message").textContent.startsWith("Plan ready"), "plan is built through the API");
check(el("plan").children.length > 0, "plan details are shown");
check(el("approve-button").disabled === false, "approve is on after the plan");
check(el("run-button").disabled === true, "run stays off until the plan is approved");

await click("approve-button");
check(el("approval-status").textContent.startsWith("Approved for one run"), "approval is issued");
check(el("run-button").disabled === false, "run is on after approval");

await click("run-button");
check(el("run-status").textContent.startsWith("Generated run_"), "the run generates an image");
check(String(el("output").src).startsWith("/api/runs/run_") && el("output").hidden === false, "image is shown");
const image = await realFetch(base + el("output").src);
check(image.status === 200 && image.headers.get("content-type") === "image/png", "image is served as PNG");
check(el("run-button").disabled === true, "the approval was spent: run is off again");
check(verdicts.every((b) => b.disabled === false), "review buttons are on for a generated image");

await clickVerdict("targeted_fix");
check(el("review-status").textContent.startsWith("note_required"), "targeted fix without a note is refused");
el("review-note").value = "crop the left edge";
await clickVerdict("targeted_fix");
check(el("review-status").textContent === "Saved verdict: targeted_fix.", "targeted fix with a note is saved");

await click("evaluate-button");
check(el("evaluation-status").textContent === "Saved rating 4.", "rating is saved");
check(el("runs").children.length === rowsAtStart + 1, "history lists the run");
check(el("preferences").children.some((li) => li.textContent.includes("average")), "preferences update");

await click("approve-button");
await click("run-button");
check(el("runs").children.length === rowsAtStart + 2, "a second run needs and uses its own approval");

el("prompt").value = "Make a flat logo of a harbor.";
for (const fn of el("prompt").listeners.input || []) fn({});
check(el("brief-message").textContent.startsWith("The brief changed"), "editing the brief drops the plan");
check(el("approve-button").disabled === true, "approve is off after an edit");

console.log(failures.length ? `${failures.length} check(s) failed` : "all checks passed");
process.exit(failures.length ? 1 : 0);
