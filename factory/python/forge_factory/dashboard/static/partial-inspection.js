(() => {
  const panel = document.getElementById("partial-inspection");
  const form = panel.querySelector("form");
  const score = panel.querySelector("[data-score]");
  const findings = panel.querySelector("ul");
  const status = panel.querySelector("[data-status]");
  const approve = panel.querySelector("[data-approve]");
  const message = panel.querySelector("[data-message]");
  const threshold = form.elements.threshold;
  const enabled = form.elements.enabled;
  const automatic = form.elements.automatic;
  let selectedOrder, url, report, dirty, pending, requestId = 0;

  const labels = {
    DISABLED: "Continue with gaps is off.",
    WAITING_FOR_EVIDENCE: "Waiting for the frozen SWE.1 inspection evidence.",
    PASS: "All scoped checks passed.",
    HOLD: "Held for rework or review.",
    ELIGIBLE: "Eligible after bounded rework.",
    REVIEW_REQUIRED: "Human review required.",
  };
  function draw(data) {
    report = data;
    form.hidden = !data.supported || Boolean(data.continued);
    approve.hidden = !(data.review_window && data.status === "REVIEW_REQUIRED");
    const checked = data.evidence;
    score.textContent = checked ?
      `${checked.passed}/${checked.total} checks passed · ${data.percentage}% · threshold ${data.settings.threshold}%` : "";
    status.textContent = data.continued ? "Continued with gaps to SWE.2." : labels[data.status] ||
      "This order has no partial-inspection route to SWE.2.";
    if (data.review_window && checked) {
      status.textContent += " Review closes at " + new Date(data.review_window.expires_at).toLocaleTimeString() + ".";
    }
    const rows = (checked?.findings || []).map(finding => {
      const item = document.createElement("li");
      const proposal = data.impact?.findings?.[finding.finding_id];
      item.textContent = [finding.requirement_id, finding.criterion, finding.severity, finding.evidence,
        finding.required_action, proposal?.disposition?.replaceAll("_", " "), proposal?.rationale, finding.owner,
        finding.revalidation?.join(" and ")].filter(Boolean).join(" · ");
      return item;
    });
    for (const hold of checked?.holds || []) {
      const item = document.createElement("li");
      item.textContent = hold.toLowerCase().replaceAll("_", " ");
      rows.push(item);
    }
    findings.replaceChildren(...rows);
    if (!dirty && data.settings) {
      threshold.value = data.settings.threshold;
      enabled.checked = data.settings.enabled;
      automatic.checked = data.settings.automatic;
      automatic.disabled = !enabled.checked;
    }
  }
  window.updatePartialInspection = async (order, line) => {
    const orderKey = order && (!line || line === "local") ? order : "";
    panel.hidden = !orderKey;
    if (!orderKey) {
      selectedOrder = undefined;
      requestId++;
      return;
    }
    if (selectedOrder !== orderKey) {
      selectedOrder = orderKey;
      url = "/partial-inspection.json?" + new URLSearchParams({line: "local", order});
      dirty = false;
      report = undefined;
      message.textContent = "";
      draw({});
    }
    if (pending) return;
    const id = ++requestId;
    try {
      const response = await fetch(url, {cache: "no-store"});
      if (id !== requestId) return;
      if (!response.ok) {
        panel.hidden = response.status === 404;
        if (!panel.hidden) status.textContent = "Omniverse inspection settings are unavailable.";
        return;
      }
      const data = await response.json();
      if (id === requestId) draw(data);
    } catch {
      if (id === requestId) status.textContent = "Omniverse inspection settings are unavailable.";
    }
  };
  async function send(body) {
    if (pending || !report?.supported) return;
    pending = true;
    requestId++;
    const order = selectedOrder;
    message.textContent = "Saving…";
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-Forge-Control": "partial-inspection"},
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (order !== selectedOrder) return;
      if (!response.ok) {
        message.textContent = data.error || "The change could not be saved.";
        if (response.status === 409) dirty = false;
        return;
      }
      dirty = false;
      draw(data);
      message.textContent = body.action === "approve" ? "Review recorded." : "Settings saved.";
    } catch {
      if (order === selectedOrder) message.textContent = "Omniverse inspection settings are unavailable.";
    } finally {
      pending = false;
    }
  }
  form.addEventListener("input", () => {
    dirty = true;
    automatic.disabled = !enabled.checked;
    if (!enabled.checked) automatic.checked = false;
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    if (form.reportValidity()) send({action: "configure", revision: report?.settings.revision,
      threshold: threshold.valueAsNumber, enabled: enabled.checked, automatic: automatic.checked});
  });
  approve.addEventListener("click", () => send({action: "approve", evidence_sha256: report?.evidence_sha256}));
})();
