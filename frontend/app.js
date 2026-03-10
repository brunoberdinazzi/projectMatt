const form = document.getElementById("report-form");
const statusElement = document.getElementById("status");
const reviewButton = document.getElementById("review-button");
const submitButton = document.getElementById("submit-button");
const ollamaModelsHint = document.getElementById("ollama-models-hint");
const ollamaModelSelect = document.getElementById("local_model");
const parserProfileSelect = document.getElementById("parser_profile");
const parserProfileHint = document.getElementById("parser-profile-hint");
const reviewPanel = document.getElementById("review-panel");
const reviewMeta = document.getElementById("review-meta");
const reviewWarnings = document.getElementById("review-warnings");
const reviewItems = document.getElementById("review-items");
const reviewPages = document.getElementById("review-pages");
const reviewSummary = document.getElementById("review-summary");
const reviewPrompt = document.getElementById("review-prompt");
const scrapeForm = document.getElementById("scrape-form");
const scrapeStatusElement = document.getElementById("scrape-status");
const scrapeButton = document.getElementById("scrape-button");
const scrapeResultElement = document.getElementById("scrape-result");

let currentReview = null;
let reviewIsStale = false;

loadOllamaModels();
loadParserProfiles();
bindFormInvalidation();

form.addEventListener("submit", (event) => {
  event.preventDefault();
});

reviewButton.addEventListener("click", async () => {
  const formData = new FormData(form);
  const file = formData.get("file");
  if (!(file instanceof File) || file.size === 0) {
    updateStatus("Selecione uma planilha Excel valida.", true);
    return;
  }

  reviewButton.disabled = true;
  submitButton.disabled = true;
  updateStatus("Analisando planilha, raspando fontes e montando o contexto...", false);

  try {
    const response = await fetch("/analysis/review", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const detail = await extractError(response);
      throw new Error(detail);
    }

    currentReview = await response.json();
    reviewIsStale = false;
    renderReview(currentReview);
    submitButton.disabled = false;
    updateStatus(
      `Analise #${currentReview.analysis_id} pronta. Revise o contexto abaixo e gere o relatorio.`,
      false
    );
  } catch (error) {
    currentReview = null;
    reviewPanel.hidden = true;
    updateStatus(error.message || "Falha ao analisar a planilha.", true);
  } finally {
    reviewButton.disabled = false;
  }
});

submitButton.addEventListener("click", async () => {
  if (!currentReview) {
    updateStatus("Analise o contexto antes de gerar o relatorio.", true);
    return;
  }
  if (reviewIsStale) {
    updateStatus("O formulario foi alterado. Reanalise a planilha antes de gerar o relatorio.", true);
    submitButton.disabled = true;
    return;
  }

  const formData = new FormData();
  const templateFile = document.getElementById("template_file").files[0];
  if (templateFile) {
    formData.append("template_file", templateFile);
  }
  formData.append("output_format", form.elements.output_format.value || "docx");
  formData.append("generation_mode", form.elements.generation_mode.value || "auto");
  formData.append("local_model", form.elements.local_model.value || "");

  submitButton.disabled = true;
  reviewButton.disabled = true;
  updateStatus("Gerando relatorio a partir da analise revisada...", false);

  try {
    const response = await fetch(`/analysis/${currentReview.analysis_id}/report`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const detail = await extractError(response);
      throw new Error(detail);
    }

    const blob = await response.blob();
    const fileName = getFileName(response) || buildFallbackName(new FormData(form));
    const analysisId = response.headers.get("x-analysis-id");
    const provider = response.headers.get("x-generation-provider");
    const model = response.headers.get("x-generation-model");
    downloadBlob(blob, fileName);
    updateStatus(
      [
        `Relatorio gerado com sucesso: ${fileName}`,
        analysisId ? `Analise #${analysisId}` : null,
        provider ? `Provedor: ${provider}` : null,
        model ? `Modelo: ${model}` : null,
      ]
        .filter(Boolean)
        .join(" | "),
      false
    );
  } catch (error) {
    updateStatus(error.message || "Falha ao gerar o relatorio.", true);
  } finally {
    submitButton.disabled = false;
    reviewButton.disabled = false;
  }
});

scrapeForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const url = document.getElementById("scrape_url").value.trim();
  const maxLinks = document.getElementById("scrape_max_links").value || "40";
  const crawlDepth = document.getElementById("scrape_depth").value || "1";
  const maxPages = document.getElementById("scrape_max_pages").value || "4";
  if (!url) {
    updateScrapeStatus("Informe uma URL para analise.", true);
    return;
  }

  scrapeButton.disabled = true;
  scrapeResultElement.hidden = true;
  scrapeResultElement.innerHTML = "";
  updateScrapeStatus("Analisando pagina e contextualizando links...", false);

  try {
    const query = new URLSearchParams({
      url,
      max_links: maxLinks,
      crawl_depth: crawlDepth,
      max_pages: maxPages,
    });
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

function bindFormInvalidation() {
  for (const element of form.elements) {
    if (element.id === "template_file") {
      continue;
    }
    element.addEventListener("change", markReviewAsStale);
    element.addEventListener("input", markReviewAsStale);
  }
}

function markReviewAsStale() {
  if (!currentReview || reviewIsStale) {
    return;
  }
  reviewIsStale = true;
  submitButton.disabled = true;
  updateStatus("O formulario mudou. Clique em 'Analisar contexto' novamente.", true);
}

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

async function loadParserProfiles() {
  try {
    const response = await fetch("/parser/profiles");
    if (!response.ok) {
      throw new Error("Falha ao consultar os perfis do parser.");
    }
    const profiles = await response.json();
    parserProfileSelect.innerHTML = "";
    for (const profile of profiles) {
      const option = document.createElement("option");
      option.value = profile.key;
      option.textContent = profile.label;
      option.dataset.description = profile.description;
      option.dataset.groups = (profile.allowed_groups || []).join(", ");
      option.dataset.status = (profile.allowed_status || []).join(", ");
      parserProfileSelect.appendChild(option);
    }
    parserProfileSelect.addEventListener("change", updateParserProfileHint);
    updateParserProfileHint();
  } catch (error) {
    parserProfileHint.textContent = "Nao foi possivel listar os perfis do parser.";
  }
}

function updateParserProfileHint() {
  const option = parserProfileSelect.selectedOptions[0];
  if (!option) {
    return;
  }
  const pieces = [option.dataset.description];
  if (option.dataset.groups) {
    pieces.push(`Grupos: ${option.dataset.groups}`);
  }
  if (option.dataset.status) {
    pieces.push(`Status: ${option.dataset.status}`);
  }
  parserProfileHint.textContent = pieces.filter(Boolean).join(" | ");
}

function renderReview(payload) {
  reviewPanel.hidden = false;
  reviewMeta.innerHTML = "";
  reviewWarnings.innerHTML = "";
  reviewItems.innerHTML = "";
  reviewPages.innerHTML = "";
  reviewSummary.innerHTML = "";
  reviewPrompt.innerHTML = "";

  const metaGrid = document.createElement("div");
  metaGrid.className = "review-grid";
  const cards = [
    buildMetaCard("Analise", `#${payload.analysis_id}`),
    buildMetaCard("Perfil", payload.parsed.parser_options.profile || "default"),
    buildMetaCard("Grupos", (payload.parsed.parser_options.allowed_groups || []).join(", ")),
    buildMetaCard("Status", (payload.parsed.parser_options.allowed_status || []).join(", ")),
    buildMetaCard("Itens", String(payload.stats.extracted_item_count)),
    buildMetaCard("Paginas", String(payload.stats.scraped_page_count)),
    buildMetaCard("Links", String(payload.stats.scraped_link_count)),
    buildMetaCard("Alertas", String(payload.stats.warning_count)),
  ];
  for (const card of cards) {
    metaGrid.appendChild(card);
  }
  reviewMeta.appendChild(metaGrid);

  renderWarnings(payload.parsed.warnings || []);
  renderItems(payload.parsed.itens_processados || []);
  renderPages(payload.parsed.scraped_pages || []);
  renderTextBlock(reviewSummary, "Resumo consolidado", payload.summary || "Sem resumo consolidado.");
  renderTextBlock(reviewPrompt, "Prompt preview", payload.prompt_preview || "Sem prompt disponivel.");
}

function buildMetaCard(label, value) {
  const card = document.createElement("article");
  card.className = "review-card";
  const heading = document.createElement("h3");
  heading.textContent = label;
  const body = document.createElement("p");
  body.textContent = value || "-";
  card.append(heading, body);
  return card;
}

function renderWarnings(warnings) {
  const container = document.createElement("section");
  container.className = "review-section";
  const title = document.createElement("h3");
  title.textContent = "Alertas do parser";
  container.appendChild(title);

  if (!warnings.length) {
    const empty = document.createElement("p");
    empty.textContent = "Nenhum alerta registrado.";
    container.appendChild(empty);
    reviewWarnings.appendChild(container);
    return;
  }

  const list = document.createElement("ul");
  list.className = "review-list";
  for (const warning of warnings) {
    const item = document.createElement("li");
    item.textContent = warning;
    list.appendChild(item);
  }
  container.appendChild(list);
  reviewWarnings.appendChild(container);
}

function renderItems(items) {
  const container = document.createElement("section");
  container.className = "review-section";
  const title = document.createElement("h3");
  title.textContent = "Itens extraidos";
  container.appendChild(title);

  if (!items.length) {
    const empty = document.createElement("p");
    empty.textContent = "Nenhum item elegivel no escopo atual.";
    container.appendChild(empty);
    reviewItems.appendChild(container);
    return;
  }

  const grid = document.createElement("div");
  grid.className = "review-grid";
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "review-card review-item-card";

    const heading = document.createElement("h4");
    heading.textContent = `${item.item_codigo} | ${item.status}`;
    card.appendChild(heading);

    const meta = document.createElement("p");
    meta.className = "review-meta-text";
    meta.textContent = [
      `Fonte: ${humanizeSource(item.fonte)}`,
      `Linha: ${item.linha_referencia}`,
      item.ano_referencia ? `Ano: ${item.ano_referencia}` : null,
    ]
      .filter(Boolean)
      .join(" | ");
    card.appendChild(meta);

    const description = document.createElement("p");
    description.textContent = item.descricao_item;
    card.appendChild(description);

    if (item.observacao) {
      const observation = document.createElement("p");
      observation.className = "review-observation";
      observation.textContent = `Observacao: ${item.observacao}`;
      card.appendChild(observation);
    }

    if (Array.isArray(item.detalhes) && item.detalhes.length) {
      const details = document.createElement("ul");
      details.className = "review-list";
      for (const detail of item.detalhes) {
        const line = document.createElement("li");
        line.textContent = `${detail.descricao}: ${detail.status}`;
        details.appendChild(line);
      }
      card.appendChild(details);
    }

    grid.appendChild(card);
  }

  container.appendChild(grid);
  reviewItems.appendChild(container);
}

function renderPages(pages) {
  const container = document.createElement("section");
  container.className = "review-section";
  const title = document.createElement("h3");
  title.textContent = "Paginas raspadas";
  container.appendChild(title);

  if (!pages.length) {
    const empty = document.createElement("p");
    empty.textContent = "Nenhuma pagina raspada nesta analise.";
    container.appendChild(empty);
    reviewPages.appendChild(container);
    return;
  }

  const grid = document.createElement("div");
  grid.className = "review-grid";
  for (const page of pages) {
    const card = document.createElement("article");
    card.className = "review-card";

    const heading = document.createElement("h4");
    heading.textContent = `${humanizeSource(page.fonte)} | ${page.page_title || "Pagina sem titulo"}`;
    card.appendChild(heading);

    const summary = document.createElement("p");
    summary.textContent = page.summary;
    card.appendChild(summary);

    const linkMeta = document.createElement("p");
    linkMeta.className = "review-meta-text";
    linkMeta.textContent = [
      page.final_url,
      `${Array.isArray(page.links) ? page.links.length : 0} link(s)`,
      `Profundidade: ${page.discovery_depth ?? 0}`,
      page.discovered_from_label ? `Via: ${page.discovered_from_label}` : null,
      typeof page.page_score === "number" && page.page_score > 0 ? `Score: ${page.page_score}` : null,
    ]
      .filter(Boolean)
      .join(" | ");
    card.appendChild(linkMeta);

    const topLinks = (page.links || []).slice(0, 4);
    if (topLinks.length) {
      const list = document.createElement("ul");
      list.className = "review-list";
      for (const link of topLinks) {
        const item = document.createElement("li");
        item.textContent = [
          `${humanizeCategory(link.category)}: ${link.label || link.url}`,
          typeof link.score === "number" ? `score ${link.score}` : null,
          link.evidence_summary || null,
        ]
          .filter(Boolean)
          .join(" | ");
        list.appendChild(item);
      }
      card.appendChild(list);
    }

    grid.appendChild(card);
  }

  container.appendChild(grid);
  reviewPages.appendChild(container);
}

function renderTextBlock(target, titleText, bodyText) {
  const container = document.createElement("section");
  container.className = "review-section";
  const title = document.createElement("h3");
  title.textContent = titleText;
  container.appendChild(title);

  const pre = document.createElement("pre");
  pre.className = "review-pre";
  pre.textContent = bodyText;
  container.appendChild(pre);
  target.appendChild(container);
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
  meta.textContent = [
    `URL final: ${payload.final_url}`,
    Array.isArray(payload.discovered_pages) && payload.discovered_pages.length
      ? `${payload.discovered_pages.length} pagina(s) descoberta(s)`
      : null,
  ]
    .filter(Boolean)
    .join(" | ");
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
    detailText.textContent = [
      details.join(" | "),
      typeof link.score === "number" ? `Score: ${link.score}` : null,
    ]
      .filter(Boolean)
      .join(" | ");
    card.appendChild(detailText);

    if (link.context) {
      const context = document.createElement("p");
      context.textContent = link.context;
      card.appendChild(context);
    }

    if (link.evidence_summary) {
      const evidence = document.createElement("p");
      evidence.className = "scrape-meta";
      evidence.textContent = link.evidence_summary;
      card.appendChild(evidence);
    }

    grid.appendChild(card);
  }

  scrapeResultElement.appendChild(grid);

  const discoveredPages = Array.isArray(payload.discovered_pages) ? payload.discovered_pages : [];
  if (discoveredPages.length) {
    const discoveredSection = document.createElement("div");
    discoveredSection.className = "scrape-grid";

    for (const page of discoveredPages) {
      const card = document.createElement("article");
      card.className = "scrape-card";

      const heading = document.createElement("h4");
      heading.textContent = page.page_title || page.final_url;
      card.appendChild(heading);

      const metaLine = document.createElement("p");
      metaLine.className = "scrape-meta";
      metaLine.textContent = [
        `Profundidade: ${page.discovery_depth ?? 0}`,
        typeof page.page_score === "number" && page.page_score > 0 ? `Score: ${page.page_score}` : null,
        page.discovered_from_label ? `Via: ${page.discovered_from_label}` : null,
      ]
        .filter(Boolean)
        .join(" | ");
      card.appendChild(metaLine);

      const pageSummary = document.createElement("p");
      pageSummary.textContent = page.summary;
      card.appendChild(pageSummary);

      discoveredSection.appendChild(card);
    }

    scrapeResultElement.appendChild(discoveredSection);
  }
}

function humanizeSource(source) {
  const labels = {
    site_orgao: "Site oficial",
    portal_transparencia: "Portal",
    esic: "e-SIC",
    nao_informada: "Nao informada",
  };
  return labels[source] || source || "Nao informada";
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
