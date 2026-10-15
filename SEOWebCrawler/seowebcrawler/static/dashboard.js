const form = document.querySelector("#scan-form");
const message = document.querySelector("#scan-message");
const reportSection = document.querySelector("#report");
let keywordChart;
let pageChart;

function appendCell(row, value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value == null ? "" : String(value);
  if (className) cell.className = className;
  row.append(cell);
}

function showError(text) {
  message.textContent = text;
  message.classList.add("error");
}

function displayReport(report, jobId) {
  document.querySelector("#report-url").textContent = report.start_url;
  document.querySelector("#score").textContent = report.seo_score;
  document.querySelector("#page-count").textContent = report.pages.length;
  const broken = report.pages.flatMap(page => page.broken_links.map(link => ({ ...link, source: page.url })));
  document.querySelector("#broken-count").textContent = broken.length;
  document.querySelector("#alt-count").textContent = report.pages.reduce((sum, page) => sum + page.images_missing_alt, 0);
  document.querySelector("#generated-at").textContent = new Date(report.generated_at).toLocaleString();
  const csvLink = document.querySelector("#csv-link");
  csvLink.href = `/api/scans/${encodeURIComponent(jobId)}/report.csv`;
  csvLink.hidden = false;

  const pageBody = document.querySelector("#pages-body");
  pageBody.replaceChildren();
  for (const page of report.pages) {
    const row = document.createElement("tr");
    appendCell(row, page.url);
    appendCell(row, page.status_code ?? "blocked");
    appendCell(row, page.seo_score);
    appendCell(row, page.title || "(missing)");
    appendCell(row, `${page.internal_links.length} internal / ${page.external_links.length} external`);
    pageBody.append(row);
  }

  const totalWords = report.pages.reduce((sum, page) => sum + page.word_count, 0);
  const keywordBody = document.querySelector("#keywords-body");
  keywordBody.replaceChildren();
  for (const [keyword, count] of Object.entries(report.keyword_totals).slice(0, 20)) {
    const row = document.createElement("tr");
    appendCell(row, keyword);
    appendCell(row, count);
    appendCell(row, totalWords ? `${(count * 100 / totalWords).toFixed(2)}%` : "0.00%");
    keywordBody.append(row);
  }

  const externalBody = document.querySelector("#external-body");
  externalBody.replaceChildren();
  const externalLinks = new Map();
  for (const page of report.pages) {
    for (const target of page.external_links) {
      const entry = externalLinks.get(target) || { sources: new Set() };
      entry.sources.add(page.url);
      externalLinks.set(target, entry);
    }
  }
  if (externalLinks.size === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.className = "empty-row";
    cell.textContent = "No external links found.";
    row.append(cell);
    externalBody.append(row);
  } else {
    for (const [target, entry] of externalLinks) {
      const row = document.createElement("tr");
      appendCell(row, target);
      appendCell(row, [...entry.sources].join(", "));
      const status = report.link_statuses[target];
      appendCell(row, status == null ? "Not checked" : status);
      externalBody.append(row);
    }
  }

  const brokenBody = document.querySelector("#broken-body");
  brokenBody.replaceChildren();
  if (broken.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 3;
    cell.className = "empty-row";
    cell.textContent = "No broken links found among checked links.";
    row.append(cell);
    brokenBody.append(row);
  } else {
    for (const link of broken) {
      const row = document.createElement("tr");
      appendCell(row, link.url, "broken");
      appendCell(row, link.source);
      appendCell(row, link.status_code, "broken");
      brokenBody.append(row);
    }
  }

  if (typeof Chart !== "undefined") {
    keywordChart?.destroy();
    pageChart?.destroy();
    const keywords = Object.entries(report.keyword_totals).slice(0, 10);
    keywordChart = new Chart(document.querySelector("#keyword-chart"), {
      type: "bar",
      data: { labels: keywords.map(([word]) => word), datasets: [{ data: keywords.map(([, count]) => count), backgroundColor: "#176d50", borderRadius: 2 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
    pageChart = new Chart(document.querySelector("#page-chart"), {
      type: "bar",
      data: { labels: report.pages.map(page => new URL(page.url).pathname || "/"), datasets: [{ data: report.pages.map(page => page.seo_score), backgroundColor: "#c9643c", borderRadius: 2 }] },
      options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { grid: { display: false } }, y: { beginAtZero: true, max: 100 } } }
    });
  }
  reportSection.hidden = false;
}

async function pollJob(jobId) {
  for (let attempt = 0; attempt < 600; attempt += 1) {
    const response = await fetch(`/api/scans/${encodeURIComponent(jobId)}`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not read scan status.");
    if (result.status === "complete") return result.report;
    if (result.status === "failed") throw new Error(result.error);
    await new Promise(resolve => window.setTimeout(resolve, 1000));
  }
  throw new Error("Scan timed out in the dashboard. Check the server logs.");
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  message.classList.remove("error");
  message.textContent = "Starting bounded crawl...";
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    const response = await fetch("/api/scans", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: form.elements.url.value.trim() })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not start scan.");
    message.textContent = "Crawling pages and checking links...";
    const report = await pollJob(result.id);
    displayReport(report, result.id);
    message.textContent = "Audit complete.";
  } catch (error) {
    showError(error.message || "Scan failed.");
  } finally {
    button.disabled = false;
  }
});