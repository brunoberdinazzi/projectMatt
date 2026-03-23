import type {
  AppFormState,
  GenerationMode,
  LayoutProfile,
  OutputFormat,
  ParserProfileDefinition,
  SelectOption,
  StoredParserOptions,
} from "../types/workspace";

const SOURCE_LABELS: Record<string, string> = {
  site_orgao: "Canal principal",
  portal_transparencia: "Canal complementar",
  esic: "Canal de atendimento",
  nao_informada: "Fonte não identificada",
};

const CATEGORY_LABELS: Record<string, string> = {
  esic: "Canal de atendimento",
  portal_transparencia: "Portal complementar",
  licitacoes: "Licitações",
  contratos: "Contratos",
  obras: "Obras",
  despesas: "Despesas",
  receitas: "Receitas",
  servidores: "Servidores",
  legislacao: "Legislação",
  institucional: "Institucional",
  ouvidoria: "Ouvidoria",
  faq: "FAQ",
  outros: "Outros",
};

const DESTINATION_LABELS: Record<string, string> = {
  pagina: "Página",
  pdf: "PDF",
  csv: "CSV",
  planilha: "Planilha",
  documento: "Documento",
  arquivo: "Arquivo",
};

const GENERATION_MODE_LABELS: Record<string, string> = {
  auto: "Automático",
  local: "Ollama local",
  ai: "IA remota",
  rules: "Regras",
};

const PROVIDER_LABELS: Record<string, string> = {
  ollama: "Ollama",
  openai: "OpenAI",
  rules: "Regras locais",
};

const WORKBOOK_LAYER_LABELS: Record<string, string> = {
  checklist_scope: "Escopo de checklist",
  reference_framework: "Matriz de referência",
  entity_reference: "Referência específica da entidade",
  registry_snapshot: "Registro cadastral",
  outcome_matrix: "Matriz de resultado",
  financial_overview: "Fechamento financeiro",
  financial_cost_structure: "Estrutura de custos",
  financial_results_bridge: "Ponte de resultado",
  financial_client_rollup: "Recebimentos por cliente",
  financial_contract_rollup: "Recebimentos por contrato",
};

const REFERENCE_LINK_KIND_LABELS: Record<string, string> = {
  primary: "Estruturado",
  reference: "Referencial",
};

const FINANCIAL_LINE_TYPE_LABELS: Record<string, string> = {
  revenue: "Receita",
  deduction: "Dedução",
  expense: "Despesa",
  result: "Resultado",
  balance: "Saldo",
  note: "Nota",
};

const FINANCIAL_ENTRY_TYPE_LABELS: Record<string, string> = {
  receivable: "Recebível",
  receivables: "Recebíveis",
  receivable_open: "Recebível em aberto",
  other_income: "Outras entradas",
  tax: "Impostos",
  personnel: "Pessoal",
  fixed_cost: "Custo fixo",
  operating_cost: "Custo operacional",
  permuta: "Permuta",
  debt: "Dívida",
  bank_fee: "Tarifa bancária",
  internal_transfer: "Transferência interna",
  summary: "Resumo",
};

const FINANCIAL_SOURCE_KIND_LABELS: Record<string, string> = {
  workbook: "Planilha",
  bank_statement: "Extrato",
};

const FINANCIAL_RECONCILIATION_STATUS_LABELS: Record<string, string> = {
  matched: "Confirmado",
  probable: "Provável",
  unmatched: "Sem pareamento",
  excluded: "Fora do escopo",
};

export const INITIAL_FORM_STATE: AppFormState = {
  file: null,
  files: [],
  templateFile: null,
  outputFormat: "docx",
  generationMode: "auto",
  localModel: "",
  parserProfile: "auto",
  allowedGroups: "",
  allowedStatus: "",
  checklistSheetName: "",
  periodoAnalise: "",
  numeroRelatorio: "",
  solicitacao: "",
  requesterArea: "",
  referencia: "",
  cidadeEmissao: "",
  dataEmissao: "",
  periodoColeta: "",
  relatorioContabilReferencia: "",
  equipeTecnica: "",
  orgao: "",
  layoutProfile: "",
  scrapeUrl: "",
  scrapeMaxLinks: "40",
  scrapeDepth: "1",
  scrapeMaxPages: "4",
};

export const GENERATION_MODE_HINTS: Record<GenerationMode, string> = {
  auto: "Equilibra qualidade e resiliência com fallback entre provedores e regras locais.",
  local: "Força a redação no Ollama local e respeita o modelo selecionado.",
  ai: "Usa o provedor remoto configurado no backend para compor o texto.",
  rules: "Ignora IA e gera o conteúdo com regras locais determinísticas.",
};

export const GENERATION_MODE_OPTIONS: SelectOption<GenerationMode>[] = [
  { value: "auto", label: "Automático" },
  { value: "local", label: "Local (Ollama)" },
  { value: "ai", label: "IA remota" },
  { value: "rules", label: "Regras" },
];

export const OUTPUT_FORMAT_OPTIONS: SelectOption<OutputFormat>[] = [
  { value: "docx", label: "DOCX" },
  { value: "pdf", label: "PDF" },
];

export const LAYOUT_OPTIONS: SelectOption<LayoutProfile>[] = [
  { value: "", label: "Detectar automaticamente" },
  { value: "profile_a", label: "Perfil A" },
  { value: "profile_b", label: "Perfil B" },
];

export function buildReviewFormData(formState: AppFormState): FormData {
  const formData = new FormData();
  const workbookFiles = formState.files.length ? formState.files : formState.file ? [formState.file] : [];
  if (workbookFiles.length > 1) {
    for (const file of workbookFiles) {
      formData.append("files", file);
    }
  } else if (formState.file) {
    formData.append("file", formState.file);
  }
  appendFormValue(formData, "parser_profile", formState.parserProfile);
  appendFormValue(formData, "allowed_groups", formState.allowedGroups);
  appendFormValue(formData, "allowed_status", formState.allowedStatus);
  appendFormValue(formData, "checklist_sheet_name", formState.checklistSheetName);
  appendFormValue(formData, "periodo_analise", formState.periodoAnalise);
  appendFormValue(formData, "numero_relatorio", formState.numeroRelatorio);
  appendFormValue(formData, "requester_area", formState.requesterArea);
  appendFormValue(formData, "referencia", formState.referencia);
  appendFormValue(formData, "solicitacao", formState.solicitacao);
  appendFormValue(formData, "cidade_emissao", formState.cidadeEmissao);
  appendFormValue(formData, "data_emissao", formState.dataEmissao);
  appendFormValue(formData, "periodo_coleta", formState.periodoColeta);
  appendFormValue(formData, "relatorio_contabil_referencia", formState.relatorioContabilReferencia);
  appendFormValue(formData, "equipe_tecnica", formState.equipeTecnica);
  appendFormValue(formData, "orgao", formState.orgao);
  appendFormValue(formData, "layout_profile", formState.layoutProfile);
  return formData;
}

export function buildGenerateFormData(formState: AppFormState): FormData {
  const formData = new FormData();
  if (formState.templateFile) {
    formData.append("template_file", formState.templateFile);
  }
  appendFormValue(formData, "output_format", formState.outputFormat || "docx");
  appendFormValue(formData, "generation_mode", formState.generationMode || "auto");
  appendFormValue(formData, "local_model", formState.localModel);
  return formData;
}

export function appendFormValue(
  formData: FormData,
  key: string,
  value: string | number | File | null | undefined
): void {
  if (value == null) {
    return;
  }
  if (typeof value === "string" && value.trim() === "") {
    return;
  }
  formData.append(key, typeof value === "number" ? String(value) : value);
}

export async function extractError(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || "Falha na operação.";
  }
  const text = await response.text();
  return text || "Falha na operação.";
}

export function getFileName(response: Response): string | null {
  const header = response.headers.get("content-disposition");
  if (!header) {
    return null;
  }
  const match = header.match(/filename=\"?([^"]+)\"?/i);
  return match ? match[1] : null;
}

export function buildFallbackName(entityName?: string | null, outputFormat: string = "docx"): string {
  const base = entityName || "relatorio-tecnico";
  const slug = base
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  return `${slug || "relatorio-tecnico"}.${outputFormat || "docx"}`;
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function describeSelectedFile(file: File | null | undefined, fallback: string): string {
  if (!file) {
    return fallback;
  }
  return `${file.name} | ${Math.max(1, Math.round(file.size / 1024))} KB`;
}

export function describeSelectedFiles(files: File[] | null | undefined, fallback: string): string {
  if (!files || files.length === 0) {
    return fallback;
  }
  if (files.length === 1) {
    return describeSelectedFile(files[0], fallback);
  }
  const totalSizeKb = files.reduce((sum, file) => sum + Math.max(1, Math.round(file.size / 1024)), 0);
  return `${files.length} arquivo(s) selecionado(s) | ${totalSizeKb} KB | Primeiro: ${files[0].name}`;
}

export function buildParserProfileHint(profile?: ParserProfileDefinition | null): string {
  if (!profile) {
    return "O backend aplica o perfil escolhido antes de extrair os itens elegíveis.";
  }
  const parts = [profile.description];
  if (Array.isArray(profile.allowed_groups) && profile.allowed_groups.length) {
    parts.push(`Grupos: ${profile.allowed_groups.join(", ")}`);
  }
  if (Array.isArray(profile.allowed_status) && profile.allowed_status.length) {
    parts.push(`Status: ${profile.allowed_status.join(", ")}`);
  }
  return parts.filter(Boolean).join(" | ");
}

export function describeLocalModelSelection(
  selectedModel?: string | null,
  recommendedModel?: string | null
): string {
  if (selectedModel) {
    return selectedModel;
  }
  if (recommendedModel) {
    return `Seleção automática (${recommendedModel})`;
  }
  return "Seleção automática";
}

export function describeParseOrigin(parseCacheHit?: boolean | null): string {
  return parseCacheHit ? "Cache local" : "Leitura direta";
}

export function formatStoredSheetSelection(parserOptions?: StoredParserOptions | null): string {
  if (Array.isArray(parserOptions?.checklist_sheet_names) && parserOptions.checklist_sheet_names.length) {
    return parserOptions.checklist_sheet_names.join(", ");
  }
  if (parserOptions?.checklist_sheet_name && parserOptions.checklist_sheet_name !== "auto") {
    return parserOptions.checklist_sheet_name;
  }
  return "";
}

export function inferLayoutProfile(tipoOrgao?: string | null): LayoutProfile {
  if (tipoOrgao === "prefeitura") {
    return "profile_a";
  }
  if (tipoOrgao === "camara") {
    return "profile_b";
  }
  return "";
}

export function humanizeParserProfile(profileKey?: string | null, fallback?: string): string {
  const labels: Record<string, string> = {
    auto: "Automático",
    default: "Padrão",
    extended: "Estendido",
    full: "Completo",
    financial_dre: "Financeiro / DRE",
  };
  const normalizedKey = profileKey ?? "";
  return labels[normalizedKey] || fallback || profileKey || "Padrão";
}

export function formatCurrency(value: number | string | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function formatCompactCurrency(value: number | string | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  const numericValue = Number(value);
  const absoluteValue = Math.abs(numericValue);
  if (absoluteValue >= 1_000_000) {
    return `${numericValue < 0 ? "-" : ""}R$\u00A0${(absoluteValue / 1_000_000).toFixed(2).replace(".", ",")} mi`;
  }
  if (absoluteValue >= 1_000) {
    return `${numericValue < 0 ? "-" : ""}R$\u00A0${(absoluteValue / 1_000).toFixed(1).replace(".", ",")} mil`;
  }
  return formatCurrency(numericValue);
}

export function formatPercent(value: number | string | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) {
    return "-";
  }
  return new Intl.NumberFormat("pt-BR", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Number(value));
}

export function humanizeSource(source?: string | null): string {
  return (source ? SOURCE_LABELS[source] : undefined) || source || "Fonte não identificada";
}

export function humanizeCategory(category?: string | null): string {
  return (category ? CATEGORY_LABELS[category] : undefined) || category || "Outros";
}

export function humanizeDestination(destination?: string | null): string {
  return (destination ? DESTINATION_LABELS[destination] : undefined) || destination || "Página";
}

export function humanizeGenerationMode(mode?: string | null): string {
  return (mode ? GENERATION_MODE_LABELS[mode] : undefined) || mode || "Não informado";
}

export function humanizeProvider(provider?: string | null): string {
  return (provider ? PROVIDER_LABELS[provider] : undefined) || provider || "Não informado";
}

export function humanizeLayerType(layerType?: string | null): string {
  return (layerType ? WORKBOOK_LAYER_LABELS[layerType] : undefined) || layerType || "Camada não identificada";
}

export function humanizeReferenceLinkKind(linkKind?: string | null): string {
  return (linkKind ? REFERENCE_LINK_KIND_LABELS[linkKind] : undefined) || linkKind || "Referencial";
}

export function humanizeFinancialLineType(lineType?: string | null): string {
  return (lineType ? FINANCIAL_LINE_TYPE_LABELS[lineType] : undefined) || lineType || "Linha";
}

export function humanizeFinancialEntryType(entryType?: string | null): string {
  return (entryType ? FINANCIAL_ENTRY_TYPE_LABELS[entryType] : undefined) || entryType || "Lançamento";
}

export function humanizeFinancialSourceKind(sourceKind?: string | null): string {
  return (sourceKind ? FINANCIAL_SOURCE_KIND_LABELS[sourceKind] : undefined) || sourceKind || "Origem não informada";
}

export function humanizeFinancialReconciliationStatus(status?: string | null): string {
  return (
    (status ? FINANCIAL_RECONCILIATION_STATUS_LABELS[status] : undefined) ||
    status ||
    "Sem classificação"
  );
}

export function toneForFinancialReconciliationStatus(status?: string | null) {
  if (status === "matched") {
    return "ready";
  }
  if (status === "probable") {
    return "warning";
  }
  if (status === "unmatched") {
    return "error";
  }
  return "neutral";
}

export function humanizeStatusTone(status?: string | null): string {
  if (status === "Sim") {
    return "ready";
  }
  if (status === "Nao") {
    return "error";
  }
  if (status === "Parcialmente") {
    return "warning";
  }
  return "neutral";
}

export function formatGenerationDate(value?: string | null): string {
  if (!value) {
    return "";
  }
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const parsedDate = new Date(normalized);
  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsedDate);
}

export function formatDuration(value: number | string | null | undefined): string {
  const durationMs = parseDurationValue(value);
  if (durationMs == null) {
    return "-";
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`;
  }
  if (durationMs < 60000) {
    return `${(durationMs / 1000).toFixed(1)} s`;
  }
  const totalSeconds = Math.round(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes} min ${String(seconds).padStart(2, "0")} s`;
}

export function isLikelyUrl(value?: string | null): boolean {
  return /^https?:\/\//i.test(value || "");
}

export function parseDurationValue(value: number | string | null | undefined): number | null {
  if (value == null || value === "") {
    return null;
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue < 0) {
    return null;
  }
  return Math.round(numericValue);
}
