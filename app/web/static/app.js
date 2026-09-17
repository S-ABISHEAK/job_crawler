// Vanilla JS -- no build step, no external dependencies.

document.addEventListener("change", async (event) => {
  const select = event.target.closest(".status-select");
  if (!select) return;

  const postingId = select.dataset.postingId;
  const status = select.value;

  try {
    const resp = await fetch(`/postings/${postingId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    if (!resp.ok) throw new Error(`Status update failed: ${resp.status}`);
    select.classList.add("saved");
    setTimeout(() => select.classList.remove("saved"), 600);
    if (window.location.pathname === "/pipeline") {
      window.location.reload();
    }
  } catch (err) {
    alert("Failed to update status: " + err.message);
  }
});

document.addEventListener("submit", async (event) => {
  const form = event.target.closest("form.outreach-form");
  if (!form) return;
  event.preventDefault();

  const postingId = form.dataset.postingId;
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  try {
    const resp = await fetch(`/postings/${postingId}/outreach`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(`Outreach save failed: ${resp.status}`);
    window.location.reload();
  } catch (err) {
    alert("Failed to save outreach entry: " + err.message);
  }
});
