const url = document.querySelector("#url");
const title = document.querySelector("#title");
const text = document.querySelector("#text");
const status = document.querySelector("#status");

async function initialize() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  url.value = tab?.url ?? "";
  title.value = tab?.title ?? "";
  if (tab?.id) {
    const [{ result = "" } = {}] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => String(window.getSelection()?.toString() ?? "").slice(0, 20000),
    });
    text.value = result;
  }
}

document.querySelector("#capture").addEventListener("click", async () => {
  status.textContent = "Importing…";
  try {
    const response = await fetch("http://127.0.0.1:8000/api/v1/data/manual-import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: url.value,
        title: title.value || null,
        selected_text: text.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    status.textContent = payload.duplicate ? "Already present in MIRSAD." : "Imported into local MIRSAD.";
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : "Import failed.";
  }
});

initialize().catch(() => {
  status.textContent = "The active tab could not be inspected.";
});
