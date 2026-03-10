const form = document.getElementById("report-form");
const statusElement = document.getElementById("status");
const submitButton = document.getElementById("submit-button");
const ollamaModelsHint = document.getElementById("ollama-models-hint");
const ollamaModelSelect = document.getElementById("local_model");
const scrapeForm = document.getElementById("scrape-form");
const scrapeStatusElement = document.getElementById("scrape-status");
const scrapeButton = document.getElementById("scrape-button");
const scrapeResultElement = document.getElementById("scrape-result");

loadOllamaModels();

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const formData = new FormData(form);
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    updateStatus("Selecione uma planilha Excel valida.", true);
    return;
  }

  submitButton.disabled = true;
  updateStatus("Processando planilha e gerando relatorio...", false);

  try {
    const response = await fetch("/report/generate", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const detail = await extractError(response);
      throw new Error(detail);
    }

    const blob = await response.blob();
    const fileName = getFileName(response) || buildFallbackName(formData);
    const analysisId = response.headers.get("x-analysis-id");
    downloadBlob(blob, fileName);
    updateStatus(
      analysisId
        ? `Relatorio gerado com sucesso: ${fileName} | Analise #${analysisId} salva no banco`
        : `Relatorio gerado com sucesso: ${fileName}`,
      false
    );
  } catch (error) {
    updateStatus(error.message || "Falha ao gerar o relatorio.", true);
  } finally {
    submitButton.disabled = false;
  }
});

scrapeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const url = document.getElementById("scrape_url").value.trim();
  const maxLinks = document.getElementById("scrape_max_links").value || "40";
  if (!url) {
    updateScrapeStatus("Informe uma URL para analise.", true);
    return;
  }

  scrapeButton.disabled = true;
  scrapeResultElement.hidden = true;
  scrapeResultElement.innerHTML = "";
  updateScrapeStatus("Analisando pagina e contextualizando links...", false);

  try {
    const query = new URLSearchParams({ url, max_links: maxLinks });
    const response = await fetch(`/scrape/links?${query.toString()}`);
    if (!response.ok) {
      const detail = await extractError(response);
      throw new Error(detail);
    }

    const payload = await response.json();
    renderScrapeResult(payload);
    updateScrapeStatus("Links analisados com sucesso.", false);
  } catch (error) {
    updateScrapeStatus(error.message || "Falha ao analisar a pagina.", true);
  } finally {
    scrapeButton.disabled = false;
  }
});

async function loadOllamaModels() {
  try {
    const response = await fetch("/providers/ollama/models");
    if (!response.ok) {
      throw new Error("Falha ao consultar modelos locais.");
    }

    const payload = await response.json();
    const models = Array.isArray(payload.models) ? payload.models : [];

    ollamaModelSelect.innerHTML = "";
    const automaticOption = document.createElement("option");
    automaticOption.value = "";
    automaticOption.textContent = "Selecao automatica";
    ollamaModelSelect.appendChild(automaticOption);

    for (const model of models) {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      ollamaModelSelect.appendChild(option);
    }

    ollamaModelsHint.textContent = models.length
      ? `Modelos detectados: ${models.join(", ")}`
      : "Nenhum modelo local detectado.";
  } catch (error) {
    ollamaModelsHint.textContent = "Nao foi possivel listar os modelos do Ollama.";
  }
}

function updateStatus(message, isError) {
  statusElement.textContent = message;
  statusElement.dataset.error = isError ? "true" : "false";
}

function updateScrapeStatus(message, isError) {
  scrapeStatusElement.textContent = message;
  scrapeStatusElement.dataset.error = isError ? "true" : "false";
}

function getFileName(response) {
  const header = response.headers.get("content-disposition");
  if (!header) return null;
  const match = header.match(/filename=\"?([^"]+)\"?/i);
  return match ? match[1] : null;
}

function buildFallbackName(formData) {
  const format = formData.get("output_format") || "docx";
  return `relatorio-tecnico.${format}`;
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function extractError(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json();
    return payload.detail || "Falha ao gerar o relatorio.";
  }

  const text = await response.text();
  return text || "Falha ao gerar o relatorio.";
}

function renderScrapeResult(payload) {
  scrapeResultElement.innerHTML = "";
  scrapeResultElement.hidden = false;

  const summaryCard = document.createElement("article");
  summaryCard.className = "scrape-summary";

  const title = document.createElement("h3");
  title.textContent = payload.page_title || "Pagina analisada";
  summaryCard.appendChild(title);

  const summary = document.createElement("p");
  summary.textContent = payload.summary;
  summaryCard.appendChild(summary);

  const meta = document.createElement("p");
  meta.className = "scrape-meta";
  meta.textContent = `URL final: ${payload.final_url}`;
  summaryCard.appendChild(meta);

  scrapeResultElement.appendChild(summaryCard);

  if (Array.isArray(payload.warnings) && payload.warnings.length) {
    const warningList = document.createElement("ul");
    warningList.className = "scrape-warning-list";
    for (const warning of payload.warnings) {
      const item = document.createElement("li");
      item.textContent = warning;
      warningList.appendChild(item);
    }
    scrapeResultElement.appendChild(warningList);
  }

  const links = Array.isArray(payload.links) ? payload.links : [];
  if (!links.length) {
    return;
  }

  const grid = document.createElement("div");
  grid.className = "scrape-grid";

  for (const link of links) {
    const card = document.createElement("article");
    card.className = "scrape-card";

    const cardHeader = document.createElement("div");
    cardHeader.className = "scrape-card-header";

    const heading = document.createElement("h4");
    heading.textContent = link.label || link.url;
    cardHeader.appendChild(heading);

    const badge = document.createElement("span");
    badge.className = "scrape-badge";
    badge.textContent = humanizeCategory(link.category);
    cardHeader.appendChild(badge);

    card.appendChild(cardHeader);

    const urlElement = document.createElement("a");
    urlElement.href = link.url;
    urlElement.target = "_blank";
    urlElement.rel = "noreferrer";
    urlElement.textContent = link.url;
    card.appendChild(urlElement);

    const details = [];
    if (link.section) {
      details.push(`Secao: ${link.section}`);
    }
    details.push(link.is_internal ? "Link interno" : "Link externo");
    details.push(`Destino: ${humanizeDestination(link.destination_type)}`);

    const detailText = document.createElement("p");
    detailText.className = "scrape-meta";
    detailText.textContent = details.join(" | ");
    card.appendChild(detailText);

    if (link.context) {
      const context = document.createElement("p");
      context.textContent = link.context;
      card.appendChild(context);
    }

    grid.appendChild(card);
  }

  scrapeResultElement.appendChild(grid);
}

function humanizeCategory(category) {
  const labels = {
    esic: "e-SIC",
    portal_transparencia: "Portal",
    licitacoes: "Licitacoes",
    contratos: "Contratos",
    obras: "Obras",
    despesas: "Despesas",
    receitas: "Receitas",
    servidores: "Servidores",
    legislacao: "Legislacao",
    institucional: "Institucional",
    ouvidoria: "Ouvidoria",
    faq: "FAQ",
    outros: "Outros",
  };
  return labels[category] || category || "Outros";
}

function humanizeDestination(destinationType) {
  const labels = {
    pagina: "Pagina",
    pdf: "PDF",
    csv: "CSV",
    planilha: "Planilha",
    documento: "Documento",
    arquivo: "Arquivo",
  };
  return labels[destinationType] || destinationType || "Pagina";
}
