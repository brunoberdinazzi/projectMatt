import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { Ref } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  Clock3,
  FileSearch,
  FileSpreadsheet,
  FileText,
  Fingerprint,
  Filter,
  Globe2,
  History,
  Layers3,
  Link2,
  Radar,
  Sparkles,
  Waypoints,
} from "lucide-react";

import {
  describeLocalModelSelection,
  formatCompactCurrency,
  describeParseOrigin,
  formatCurrency,
  formatDuration,
  formatPercent,
  formatStoredSheetSelection,
  humanizeCategory,
  humanizeFinancialEntryType,
  humanizeFinancialLineType,
  humanizeFinancialReconciliationStatus,
  humanizeFinancialSourceKind,
  humanizeGenerationMode,
  humanizeLayerType,
  humanizeParserProfile,
  humanizeProvider,
  humanizeReferenceLinkKind,
  humanizeSource,
  humanizeStatusTone,
  isLikelyUrl,
  toneForFinancialReconciliationStatus,
} from "../lib/app-utils";
import type {
  ActiveReviewTab,
  AnalysisReviewResponse,
  AsyncItemsState,
  FinancialAnalysisResult,
  FinancialClientRollup,
  FinancialContractRollup,
  FinancialPeriodSummary,
  FinancialStatementLine,
  FinancialTraceEntry,
  FinancialWarehouseOverview,
  GenerationTraceItem,
  TabDescriptor,
  WorkspaceMetric,
} from "../types/workspace";
import {
  EmptyBlock,
  GuideCard,
  MetricCard,
  PreBlock,
  ReviewSection,
  SelectField,
  StatusPill,
  TabStrip,
  Tag,
  TraceCard,
} from "./ui";

const REVIEW_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const REVIEW_PANEL_VARIANTS = {
  initial: { opacity: 0, y: 34 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 20 },
  transition: { duration: 0.4, ease: REVIEW_EASE },
};

const REVIEW_TAB_VARIANTS = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 12 },
  transition: { duration: 0.24, ease: REVIEW_EASE },
};

interface ReviewPanelProps {
  review: AnalysisReviewResponse | null;
  panelRef: Ref<HTMLElement>;
  activeTab: ActiveReviewTab | string;
  onTabChange: (tab: string) => void;
  generationHistoryState: AsyncItemsState<GenerationTraceItem>;
  highlightGenerationId: string | number | null;
  formState: {
    generationMode: string;
    outputFormat: string;
    localModel: string;
  };
  recommendedLocalModel: string;
}

function normalizeFinancialAmount(value?: number | null): number | null {
  if (value == null || Number.isNaN(Number(value))) {
    return null;
  }
  return Math.abs(Number(value));
}

function getFinancialLineAmount(financialAnalysis: FinancialAnalysisResult | null | undefined, key: string) {
  return financialAnalysis?.dre_lines?.find((line) => line.key === key)?.amount ?? null;
}

function compactEntityLabel(value?: string | null, maxLength = 30): string {
  const normalized = value?.trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "-";
  }
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength - 1).trimEnd()}...` : normalized;
}

function summarizeStoredSheetSelection(sheetNames: string[], parserOptions?: AnalysisReviewResponse["parsed"]["parser_options"]) {
  if (sheetNames.length > 3) {
    return `${sheetNames.length} abas consolidadas`;
  }
  if (sheetNames.length) {
    return sheetNames.join(", ");
  }
  return formatStoredSheetSelection(parserOptions) || "Automático";
}

function normalizeTraceText(value?: string | null): string {
  return value?.trim().replace(/\s+/g, " ").toLowerCase() || "";
}

function classifyReviewWarning(warning: string): "critical" | "attention" | "info" {
  const normalized = normalizeTraceText(warning);
  if (
    normalized.includes("erro") ||
    normalized.includes("falha") ||
    normalized.includes("nao foi possivel") ||
    normalized.includes("não foi possível")
  ) {
    return "critical";
  }
  if (
    normalized.includes("pendenc") ||
    normalized.includes("pendênc") ||
    normalized.includes("negativ") ||
    normalized.includes("aberto") ||
    normalized.includes("parcial")
  ) {
    return "attention";
  }
  return "info";
}

function summarizeReviewWarnings(warnings: string[]) {
  return warnings.reduce(
    (summary, warning) => {
      const tone = classifyReviewWarning(warning);
      summary[tone] += 1;
      return summary;
    },
    { critical: 0, attention: 0, info: 0 }
  );
}

function buildReviewWarningHeadline(
  warningSummary: ReturnType<typeof summarizeReviewWarnings>,
  totalWarnings: number,
  isFinancialAnalysis: boolean
) {
  if (warningSummary.critical > 0) {
    return {
      tone: "error" as const,
      badge: `${warningSummary.critical} crítico(s)`,
      title: `${warningSummary.critical} ponto(s) crítico(s) pedem revisão antes da exportação.`,
      copy:
        warningSummary.attention > 0
          ? `${warningSummary.attention} ponto(s) de atenção seguem abertos no recorte e podem afetar a leitura final.`
          : "Vale revisar esses sinais antes de consolidar a narrativa e gerar o documento final.",
    };
  }

  if (warningSummary.attention > 0) {
    return {
      tone: "warning" as const,
      badge: `${warningSummary.attention} atenção`,
      title: `${warningSummary.attention} ponto(s) de atenção seguem abertos no recorte.`,
      copy: isFinancialAnalysis
        ? "A base financeira está utilizável, mas ainda merece checagem nos pontos destacados antes da emissão."
        : "A base está estruturada, mas ainda merece checagem nos pontos destacados antes da composição final.",
    };
  }

  if (totalWarnings > 0) {
    return {
      tone: "neutral" as const,
      badge: `${totalWarnings} observação(ões)`,
      title: "A leitura não trouxe bloqueios, apenas observações de contexto.",
      copy: "Esses avisos ajudam a interpretar o recorte, mas não sinalizam impedimento para seguir com a revisão.",
    };
  }

  return {
    tone: "ready" as const,
    badge: "Sem bloqueios",
    title: "A leitura inicial ficou estável para seguir com a revisão.",
    copy: isFinancialAnalysis
      ? "O demonstrativo já traz um recorte consistente para validar DRE, clientes, contratos e rastreabilidade."
      : "O recorte já traz estrutura suficiente para validar itens, camadas, evidências e prompt antes da geração.",
  };
}

function buildReviewTabs(
  isFinancialAnalysis: boolean,
  financialAnalysis: FinancialAnalysisResult | null | undefined,
  reviewWarningCount: number,
  reviewLayerCount: number,
  reviewItemCount: number,
  reviewPageCount: number,
  reviewHistoryCount: number
): TabDescriptor[] {
  return [
    { key: "overview", label: "Resumo", icon: Radar, count: reviewWarningCount },
    ...(isFinancialAnalysis
      ? [{ key: "dre", label: "DRE", icon: FileSpreadsheet, count: financialAnalysis?.months?.length ?? 0 }]
      : []),
    ...(isFinancialAnalysis ? [{ key: "trace", label: "Rastro", icon: Waypoints, count: reviewItemCount }] : []),
    { key: "layers", label: "Camadas", icon: Layers3, count: reviewLayerCount },
    {
      key: "items",
      label: isFinancialAnalysis ? "Lançamentos" : "Itens",
      icon: FileSearch,
      count: reviewItemCount,
    },
    { key: "crawler", label: "Crawler", icon: Globe2, count: reviewPageCount },
    { key: "prompt", label: "Prompt", icon: FileText },
    { key: "history", label: "Histórico", icon: History, count: reviewHistoryCount },
  ];
}

function buildStatsMetrics(
  review: AnalysisReviewResponse,
  isFinancialAnalysis: boolean,
  financialAnalysis: FinancialAnalysisResult | null | undefined,
  summaryInflows: number | null,
  summaryExpenses: number | null,
  summaryNetResult: number | null
): WorkspaceMetric[] {
  if (isFinancialAnalysis) {
    return [
      {
        icon: FileSpreadsheet,
        label: "Períodos",
        value: String(financialAnalysis?.months?.length ?? 0),
      },
      {
        icon: FileSearch,
        label: "Lançamentos",
        value: String(review.stats?.extracted_item_count ?? 0),
      },
      { icon: Waypoints, label: "Entradas", value: formatCompactCurrency(summaryInflows) },
      { icon: AlertTriangle, label: "Despesas", value: formatCompactCurrency(summaryExpenses) },
      { icon: Sparkles, label: "Resultado", value: formatCompactCurrency(summaryNetResult) },
      { icon: Clock3, label: "Leitura", value: formatDuration(review.stats?.parse_duration_ms) },
      { icon: Globe2, label: "Páginas", value: String(review.stats?.scraped_page_count ?? 0) },
      { icon: Clock3, label: "Crawler", value: formatDuration(review.stats?.scrape_duration_ms) },
    ];
  }

  return [
    {
      icon: FileSearch,
      label: "Itens elegíveis",
      value: String(review.stats?.extracted_item_count ?? 0),
    },
    {
      icon: Layers3,
      label: "Camadas",
      value: String(review.parsed?.context_layers?.length ?? 0),
    },
    {
      icon: Link2,
      label: "Referências",
      value: String(review.parsed?.reference_links?.length ?? 0),
    },
    { icon: Globe2, label: "Páginas", value: String(review.stats?.scraped_page_count ?? 0) },
    { icon: Clock3, label: "Leitura", value: formatDuration(review.stats?.parse_duration_ms) },
    { icon: Clock3, label: "Crawler", value: formatDuration(review.stats?.scrape_duration_ms) },
  ];
}

function FinancialMonthCard({ month }: { month: FinancialPeriodSummary }) {
  return (
    <article className="data-card">
      <div className="card-head">
        <div>
          <h3>{month.period_label}</h3>
          <p className="meta-line">Aba {month.sheet_name}</p>
        </div>
        <StatusPill tone={(month.net_result ?? 0) >= 0 ? "ready" : "warning"} icon={FileSpreadsheet}>
          {formatCurrency(month.net_result)}
        </StatusPill>
      </div>
      <ul className="detail-list financial-detail-list">
        <li>Receita base: {formatCurrency(normalizeFinancialAmount(month.receivables_total))}</li>
        <li>Receita bruta: {formatCurrency(normalizeFinancialAmount(month.gross_revenue_total))}</li>
        <li>Outras entradas: {formatCurrency(normalizeFinancialAmount(month.other_income_total))}</li>
        <li>Custos e despesas: {formatCurrency(normalizeFinancialAmount(month.global_expenses_total))}</li>
        <li>Impostos: {formatCurrency(normalizeFinancialAmount(month.taxes_total))}</li>
        <li>Pessoal: {formatCurrency(normalizeFinancialAmount(month.personnel_total))}</li>
        <li>Custos fixos: {formatCurrency(normalizeFinancialAmount(month.fixed_costs_total))}</li>
        <li>Custos operacionais: {formatCurrency(normalizeFinancialAmount(month.operating_costs_total))}</li>
        <li>Pendências abertas: {month.pending_entry_count}</li>
        {month.closing_total != null ? <li>Saldo final informado: {formatCurrency(month.closing_total)}</li> : null}
      </ul>
    </article>
  );
}

function FinancialLineCard({ line }: { line: FinancialStatementLine }) {
  return (
    <article className="data-card financial-line-card">
      <div className="card-head">
        <div>
          <h3>{line.label}</h3>
          <p className="meta-line">
            {humanizeFinancialLineType(line.line_type)}
            {line.share_of_gross_revenue != null
              ? ` | ${formatPercent(line.share_of_gross_revenue)} da receita bruta`
              : ""}
          </p>
        </div>
        <StatusPill tone={line.amount >= 0 ? "ready" : "warning"} icon={Sparkles}>
          {formatCurrency(line.amount)}
        </StatusPill>
      </div>
    </article>
  );
}

function buildRollupReconciliationHeadline(rollup: {
  reconciliation_coverage_ratio?: number | null;
  reconciliation_matched_count?: number;
  reconciliation_probable_count?: number;
  reconciliation_unmatched_count?: number;
}) {
  const matchedCount = rollup.reconciliation_matched_count || 0;
  const probableCount = rollup.reconciliation_probable_count || 0;
  const unmatchedCount = rollup.reconciliation_unmatched_count || 0;
  const eligibleCount = matchedCount + probableCount + unmatchedCount;
  if (eligibleCount <= 0) {
    return { tone: "neutral" as const, label: "Sem base conciliável" };
  }
  const coverageRatio = rollup.reconciliation_coverage_ratio ?? 0;
  if (coverageRatio >= 0.75) {
    return { tone: "ready" as const, label: `Cobertura ${formatPercent(coverageRatio)}` };
  }
  if (coverageRatio >= 0.4) {
    return { tone: "warning" as const, label: `Cobertura ${formatPercent(coverageRatio)}` };
  }
  return { tone: "error" as const, label: `Cobertura ${formatPercent(coverageRatio)}` };
}

function FinancialRollupMetric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="financial-rollup-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TraceSummaryCard({
  icon: Icon,
  label,
  count,
  amount,
}: {
  icon: typeof CheckCircle2;
  label: string;
  count: number;
  amount: number;
}) {
  return (
    <article className="metric-card trace-summary-card">
      <div className="metric-label">
        <span className="icon-badge icon-badge-soft">
          <Icon size={16} />
        </span>
        <span>{label}</span>
      </div>
      <strong className="metric-value">{count}</strong>
      <span className="trace-summary-amount">{formatCompactCurrency(amount)}</span>
    </article>
  );
}

function FinancialClientRollupCard({ client }: { client: FinancialClientRollup }) {
  const reconciliationHeadline = buildRollupReconciliationHeadline(client);
  const coveredPeriodsLabel = client.months_covered?.length ? `${client.months_covered.length} período(s)` : "Sem período";
  const contractPreview = client.contract_labels?.slice(0, 4).join(" | ");
  return (
    <article className="data-card data-card-compact financial-rollup-card">
      <div className="card-head">
        <div>
          <h3 className="financial-rollup-title" title={client.client_name}>
            {compactEntityLabel(client.client_name, 40)}
          </h3>
          <p className="meta-line financial-rollup-meta">
            {client.contract_count} contrato(s)
            {client.months_covered?.length ? ` | ${client.months_covered.length} período(s)` : ""}
          </p>
        </div>
        <StatusPill tone={client.total_received_amount > 0 ? "ready" : "neutral"} icon={Waypoints}>
          {formatCompactCurrency(client.total_received_amount)}
        </StatusPill>
      </div>
      <div className="financial-rollup-metrics">
        <FinancialRollupMetric label="Recebido" value={formatCurrency(client.total_received_amount)} />
        <FinancialRollupMetric label="Previsto" value={formatCurrency(client.total_expected_amount)} />
        <FinancialRollupMetric label="Pendente" value={formatCurrency(client.total_pending_amount)} />
        <FinancialRollupMetric label="Escopo" value={`${client.contract_count} contratos | ${coveredPeriodsLabel}`} />
      </div>
      <div className="trace-badges financial-rollup-badges">
        <StatusPill tone={reconciliationHeadline.tone} icon={CheckCircle2}>
          {reconciliationHeadline.label}
        </StatusPill>
        {(client.reconciliation_matched_count || 0) > 0 ? (
          <Tag icon={CheckCircle2}>
            Confirmado {client.reconciliation_matched_count} |{" "}
            {formatCurrency(client.reconciliation_matched_amount)}
          </Tag>
        ) : null}
        {(client.reconciliation_probable_count || 0) > 0 ? (
          <Tag icon={AlertTriangle}>
            Provável {client.reconciliation_probable_count} |{" "}
            {formatCurrency(client.reconciliation_probable_amount)}
          </Tag>
        ) : null}
        {(client.reconciliation_alias_supported_count || 0) > 0 ? (
          <Tag icon={Fingerprint}>
            Alias canônico {client.reconciliation_alias_supported_count} |{" "}
            {formatCurrency(client.reconciliation_alias_supported_amount)}
          </Tag>
        ) : null}
      </div>
      <details className="financial-rollup-details">
        <summary>{contractPreview ? "Ver contratos e conciliação" : "Ver detalhe do cliente"}</summary>
        <ul className="detail-list financial-detail-list">
          <li>
            Conciliação do recebido:{" "}
            <strong>
              {(client.reconciliation_matched_count || 0) + (client.reconciliation_probable_count || 0)}
            </strong>{" "}
            conciliado(s) ou provável(is)
          </li>
          <li>
            Sem pareamento: <strong>{client.reconciliation_unmatched_count || 0}</strong>
            {(client.reconciliation_unmatched_amount || 0) > 0
              ? ` | ${formatCurrency(client.reconciliation_unmatched_amount)}`
              : ""}
          </li>
          {client.months_covered?.length ? <li>Períodos: {client.months_covered.join(" | ")}</li> : null}
          {contractPreview ? <li>Contratos: {contractPreview}</li> : null}
        </ul>
      </details>
    </article>
  );
}

function FinancialContractRollupCard({ contract }: { contract: FinancialContractRollup }) {
  const reconciliationHeadline = buildRollupReconciliationHeadline(contract);
  const contractPeriodsLabel = contract.months_covered?.length ? `${contract.months_covered.length} período(s)` : "Sem período";
  const contractWindow = [contract.contract_start_date, contract.contract_end_date].filter(Boolean).join(" até ");
  const sourceSheetsLabel = contract.source_sheet_names?.slice(0, 4).join(" | ");
  return (
    <article className="data-card data-card-compact financial-rollup-card financial-rollup-card-contract">
      <div className="card-head">
        <div>
          <h3 className="financial-rollup-title" title={contract.contract_label}>
            {compactEntityLabel(contract.contract_label, 52)}
          </h3>
          <p className="meta-line financial-rollup-meta">
            {contractPeriodsLabel}
            {contract.unit ? ` | ${contract.unit}` : ""}
          </p>
        </div>
        <StatusPill tone={contract.total_received_amount > 0 ? "ready" : "neutral"} icon={FileSearch}>
          {formatCompactCurrency(contract.total_received_amount)}
        </StatusPill>
      </div>
      <div className="financial-rollup-metrics">
        <FinancialRollupMetric label="Recebido" value={formatCurrency(contract.total_received_amount)} />
        <FinancialRollupMetric label="Previsto" value={formatCurrency(contract.total_expected_amount)} />
        <FinancialRollupMetric label="Pendente" value={formatCurrency(contract.total_pending_amount)} />
        <FinancialRollupMetric label="Lançamentos" value={String(contract.entry_count || 0)} />
      </div>
      <div className="trace-badges financial-rollup-badges">
        <StatusPill tone={reconciliationHeadline.tone} icon={CheckCircle2}>
          {reconciliationHeadline.label}
        </StatusPill>
        {(contract.reconciliation_matched_count || 0) > 0 ? (
          <Tag icon={CheckCircle2}>
            Confirmado {contract.reconciliation_matched_count} |{" "}
            {formatCurrency(contract.reconciliation_matched_amount)}
          </Tag>
        ) : null}
        {(contract.reconciliation_probable_count || 0) > 0 ? (
          <Tag icon={AlertTriangle}>
            Provável {contract.reconciliation_probable_count} |{" "}
            {formatCurrency(contract.reconciliation_probable_amount)}
          </Tag>
        ) : null}
        {(contract.reconciliation_alias_supported_count || 0) > 0 ? (
          <Tag icon={Fingerprint}>
            Alias canônico {contract.reconciliation_alias_supported_count} |{" "}
            {formatCurrency(contract.reconciliation_alias_supported_amount)}
          </Tag>
        ) : null}
      </div>
      <details className="financial-rollup-details">
        <summary>{sourceSheetsLabel || contract.latest_status ? "Ver detalhe do contrato" : "Ver conciliação do contrato"}</summary>
        <ul className="detail-list financial-detail-list">
          {contract.client_name ? <li>Cliente: {contract.client_name}</li> : null}
          {contractWindow ? <li>Janela conhecida: {contractWindow}</li> : null}
          <li>
            Conciliação do contrato:{" "}
            <strong>
              {(contract.reconciliation_matched_count || 0) + (contract.reconciliation_probable_count || 0)}
            </strong>{" "}
            conciliado(s) ou provável(is)
          </li>
          <li>
            Sem pareamento: <strong>{contract.reconciliation_unmatched_count || 0}</strong>
            {(contract.reconciliation_unmatched_amount || 0) > 0
              ? ` | ${formatCurrency(contract.reconciliation_unmatched_amount)}`
              : ""}
          </li>
          {contract.latest_status ? <li>Último status: {contract.latest_status}</li> : null}
          {contract.months_covered?.length ? <li>Períodos: {contract.months_covered.join(" | ")}</li> : null}
          {sourceSheetsLabel ? <li>Abas: {sourceSheetsLabel}</li> : null}
        </ul>
      </details>
    </article>
  );
}

function buildTraceQuery(
  analysisId: number,
  filters: {
    clientName: string;
    contractLabel: string;
    periodLabel: string;
    entryType: string;
    sourceKind: string;
    reconciliationStatus: string;
  }
) {
  const params = new URLSearchParams({ limit: "36" });
  if (filters.clientName) {
    params.set("client_name", filters.clientName);
  }
  if (filters.contractLabel) {
    params.set("contract_label", filters.contractLabel);
  }
  if (filters.periodLabel) {
    params.set("period_label", filters.periodLabel);
  }
  if (filters.entryType) {
    params.set("entry_type", filters.entryType);
  }
  if (filters.sourceKind) {
    params.set("source_kind", filters.sourceKind);
  }
  if (filters.reconciliationStatus) {
    params.set("reconciliation_status", filters.reconciliationStatus);
  }
  return `/analysis/${analysisId}/financial-entries?${params.toString()}`;
}

function buildTraceSummary(entries: FinancialTraceEntry[]) {
  const summary = {
    workbook: { count: 0, amount: 0 },
    bank_statement: { count: 0, amount: 0 },
    matched: { count: 0, amount: 0 },
    probable: { count: 0, amount: 0 },
    unmatched: { count: 0, amount: 0 },
    excluded: { count: 0, amount: 0 },
    alias_supported: { count: 0, amount: 0 },
  };

  for (const entry of entries) {
    const amount = Math.abs(Number(entry.amount || 0));
    if (entry.source_kind && entry.source_kind in summary) {
      const sourceBucket = summary[entry.source_kind as "workbook" | "bank_statement"];
      sourceBucket.count += 1;
      sourceBucket.amount += amount;
    }
    if (entry.reconciliation_status && entry.reconciliation_status in summary) {
      const statusBucket =
        summary[entry.reconciliation_status as "matched" | "probable" | "unmatched" | "excluded"];
      statusBucket.count += 1;
      statusBucket.amount += amount;
    }
    if (entry.reconciliation_alias_label) {
      summary.alias_supported.count += 1;
      summary.alias_supported.amount += amount;
    }
  }

  return summary;
}

function buildTraceEntryCardClass(entry: FinancialTraceEntry) {
  const parts = ["data-card", "trace-entry-card"];
  if (entry.reconciliation_status) {
    parts.push(`trace-entry-card-${entry.reconciliation_status}`);
  }
  if (entry.source_kind) {
    parts.push(`trace-entry-source-${entry.source_kind}`);
  }
  return parts.join(" ");
}

export function ReviewPanel({
  review,
  panelRef,
  activeTab,
  onTabChange,
  generationHistoryState,
  highlightGenerationId,
  formState,
  recommendedLocalModel,
}: ReviewPanelProps) {
  const analysisId = review?.analysis_id ?? 0;
  const financialAnalysis = review?.parsed?.financial_analysis ?? null;
  const warehouseOverview: FinancialWarehouseOverview | null = review?.parsed?.warehouse_overview ?? null;
  const isFinancialAnalysis = Boolean(financialAnalysis);
  const reviewWarningCount = review?.parsed?.warnings?.length ?? 0;
  const reviewItemCount = isFinancialAnalysis
    ? financialAnalysis?.entry_count ?? 0
    : review?.parsed?.itens_processados?.length ?? 0;
  const reviewLayerCount = review?.parsed?.context_layers?.length ?? 0;
  const reviewReferenceLinkCount = review?.parsed?.reference_links?.length ?? 0;
  const reviewPageCount = review?.parsed?.scraped_pages?.length ?? 0;
  const reviewHistoryCount = generationHistoryState.items.length;
  const reviewSheetNames = review?.parsed?.parser_options?.checklist_sheet_names || [];
  const clientRollups = financialAnalysis?.client_rollups ?? [];
  const contractRollups = financialAnalysis?.contract_rollups ?? [];
  const parseOriginLabel = describeParseOrigin(review?.stats?.parse_cache_hit);
  const summaryNetResult = getFinancialLineAmount(financialAnalysis, "net_result");
  const summaryInflows = getFinancialLineAmount(financialAnalysis, "operating_inflows");
  const summaryExpenses = getFinancialLineAmount(financialAnalysis, "global_expenses");
  const warehouseTopClient = warehouseOverview?.top_clients?.[0] ?? null;
  const warehouseTopContract = warehouseOverview?.top_contracts?.[0] ?? null;
  const warehouseTopPeriod = warehouseOverview?.top_periods?.[0] ?? null;
  const topClient = warehouseTopClient
    ? ({
        client_name: warehouseTopClient.client_name,
        total_received_amount: warehouseTopClient.total_received_amount,
      } as FinancialClientRollup)
    : clientRollups.reduce<FinancialClientRollup | null>((bestClient, client) => {
        if (!bestClient || client.total_received_amount > bestClient.total_received_amount) {
          return client;
        }
        return bestClient;
      }, null);
  const topContract = warehouseTopContract
    ? ({
        contract_label: warehouseTopContract.contract_label,
        total_received_amount: warehouseTopContract.total_received_amount,
      } as FinancialContractRollup)
    : contractRollups.reduce<FinancialContractRollup | null>((bestContract, contract) => {
        if (!bestContract || contract.total_received_amount > bestContract.total_received_amount) {
          return contract;
        }
        return bestContract;
      }, null);
  const financialSnapshotMetrics: WorkspaceMetric[] = isFinancialAnalysis
    ? [
        {
          icon: FileSearch,
          label: "Clientes",
          value: String(warehouseOverview?.client_count ?? clientRollups.length),
        },
        {
          icon: Layers3,
          label: "Contratos",
          value: String(warehouseOverview?.contract_count ?? contractRollups.length),
        },
        {
          icon: Waypoints,
          label: "Maior cliente",
          value: topClient
            ? `${compactEntityLabel(topClient.client_name)} | ${formatCompactCurrency(topClient.total_received_amount)}`
            : "-",
        },
        {
          icon: Sparkles,
          label: "Maior contrato",
          value: topContract
            ? `${compactEntityLabel(topContract.contract_label)} | ${formatCompactCurrency(topContract.total_received_amount)}`
            : "-",
        },
      ]
    : [];
  const [financialTraceState, setFinancialTraceState] = useState<AsyncItemsState<FinancialTraceEntry>>({
    loading: false,
    error: "",
    items: [],
  });
  const [traceFilters, setTraceFilters] = useState({
    clientName: "",
    contractLabel: "",
    periodLabel: "",
    entryType: "",
    sourceKind: "",
    reconciliationStatus: "",
  });

  useEffect(() => {
    setTraceFilters({
      clientName: "",
      contractLabel: "",
      periodLabel: "",
      entryType: "",
      sourceKind: "",
      reconciliationStatus: "",
    });
    setFinancialTraceState({ loading: false, error: "", items: [] });
  }, [analysisId]);

  useEffect(() => {
    if (analysisId <= 0 || !isFinancialAnalysis || activeTab !== "trace") {
      return;
    }
    const controller = new AbortController();

    async function loadTraceEntries() {
      setFinancialTraceState((current) => ({ ...current, loading: true, error: "" }));
      try {
        const response = await fetch(buildTraceQuery(analysisId, traceFilters), {
          credentials: "include",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Não foi possível consultar os lançamentos rastreáveis.");
        }
        const payload = (await response.json()) as FinancialTraceEntry[];
        setFinancialTraceState({
          loading: false,
          error: "",
          items: Array.isArray(payload) ? payload : [],
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setFinancialTraceState({
          loading: false,
          error: error instanceof Error ? error.message : "Falha ao carregar a rastreabilidade financeira.",
          items: [],
        });
      }
    }

    void loadTraceEntries();
    return () => controller.abort();
  }, [activeTab, analysisId, isFinancialAnalysis, traceFilters]);

  const traceClientOptions = [
    { value: "", label: "Todos os clientes" },
    ...clientRollups.map((client) => ({ value: client.client_name, label: client.client_name })),
  ];
  const traceContractOptions = [
    { value: "", label: "Todos os contratos" },
    ...contractRollups.slice(0, 30).map((contract) => ({
      value: contract.contract_label,
      label: contract.contract_label,
    })),
  ];
  const tracePeriodOptions = [
    { value: "", label: "Todos os períodos" },
    ...(financialAnalysis?.months ?? []).map((month) => ({ value: month.period_label, label: month.period_label })),
  ];
  const traceEntryTypeOptions = [
    { value: "", label: "Todos os tipos" },
    { value: "receivable", label: humanizeFinancialEntryType("receivable") },
    { value: "receivable_open", label: humanizeFinancialEntryType("receivable_open") },
    { value: "other_income", label: humanizeFinancialEntryType("other_income") },
    { value: "tax", label: humanizeFinancialEntryType("tax") },
    { value: "personnel", label: humanizeFinancialEntryType("personnel") },
    { value: "fixed_cost", label: humanizeFinancialEntryType("fixed_cost") },
    { value: "operating_cost", label: humanizeFinancialEntryType("operating_cost") },
    { value: "bank_fee", label: humanizeFinancialEntryType("bank_fee") },
    { value: "internal_transfer", label: humanizeFinancialEntryType("internal_transfer") },
    { value: "permuta", label: humanizeFinancialEntryType("permuta") },
    { value: "debt", label: humanizeFinancialEntryType("debt") },
  ];
  const traceSourceKindOptions = [
    { value: "", label: "Todas as origens" },
    { value: "workbook", label: humanizeFinancialSourceKind("workbook") },
    { value: "bank_statement", label: humanizeFinancialSourceKind("bank_statement") },
  ];
  const traceReconciliationStatusOptions = [
    { value: "", label: "Todos os status" },
    { value: "matched", label: humanizeFinancialReconciliationStatus("matched") },
    { value: "probable", label: humanizeFinancialReconciliationStatus("probable") },
    { value: "unmatched", label: humanizeFinancialReconciliationStatus("unmatched") },
    { value: "excluded", label: humanizeFinancialReconciliationStatus("excluded") },
  ];
  const traceSummary = buildTraceSummary(financialTraceState.items);
  const activeTraceFilterCount = Object.values(traceFilters).filter(Boolean).length;
  const hasTraceFilters = activeTraceFilterCount > 0;
  const latestGeneration = generationHistoryState.items[0] ?? null;
  const generationFallbackCount = generationHistoryState.items.filter((trace) => Boolean(trace.fallback_reason)).length;
  const promptPreviewLength = review?.prompt_preview?.trim().length ?? 0;

  if (!review) {
    return null;
  }

  const reviewTabs = buildReviewTabs(
    isFinancialAnalysis,
    financialAnalysis,
    reviewWarningCount,
    reviewLayerCount,
    reviewItemCount,
    reviewPageCount,
    reviewHistoryCount
  );
  const statsMetrics = buildStatsMetrics(
    review,
    isFinancialAnalysis,
    financialAnalysis,
    summaryInflows,
    summaryExpenses,
    summaryNetResult
  );
  const overviewWarnings = review.parsed?.warnings ?? [];
  const warningSummary = summarizeReviewWarnings(overviewWarnings);
  const warningHeadline = buildReviewWarningHeadline(warningSummary, overviewWarnings.length, isFinancialAnalysis);
  const overviewSummaryMetrics: WorkspaceMetric[] = isFinancialAnalysis
    ? [
        {
          icon: FileSpreadsheet,
          label: "Períodos",
          value: String(warehouseOverview?.period_count ?? financialAnalysis?.months?.length ?? 0),
        },
        {
          icon: FileSearch,
          label: "Lançamentos",
          value: String(warehouseOverview?.entry_count ?? review.stats?.extracted_item_count ?? 0),
        },
        {
          icon: Sparkles,
          label: "Resultado",
          value: formatCompactCurrency(summaryNetResult),
        },
        {
          icon: Link2,
          label: "Referências",
          value: String(reviewReferenceLinkCount),
        },
      ]
    : [
        {
          icon: FileSearch,
          label: "Itens elegíveis",
          value: String(review.stats?.extracted_item_count ?? 0),
        },
        {
          icon: Layers3,
          label: "Camadas",
          value: String(reviewLayerCount),
        },
        {
          icon: Link2,
          label: "Referências",
          value: String(reviewReferenceLinkCount),
        },
        {
          icon: Globe2,
          label: "Páginas",
          value: String(review.stats?.scraped_page_count ?? 0),
        },
      ];
  const visibleSheetNames = reviewSheetNames.slice(0, 6);
  const remainingSheetCount = Math.max(0, reviewSheetNames.length - visibleSheetNames.length);
  const visibleLayerTypes = (review.parsed?.context_layers ?? []).slice(0, 6);
  const remainingLayerCount = Math.max(0, reviewLayerCount - visibleLayerTypes.length);
  const selectedReferenceLinks = (review.parsed?.reference_links ?? []).filter((link) => link.selected_for_crawl);
  const visibleReferenceLinks = selectedReferenceLinks.slice(0, 4);
  const remainingReferenceLinkCount = Math.max(0, selectedReferenceLinks.length - visibleReferenceLinks.length);
  const visibleOverviewWarnings = overviewWarnings.slice(0, 2);
  const remainingOverviewWarningCount = Math.max(0, overviewWarnings.length - visibleOverviewWarnings.length);
  const reviewFactTags = [
    { icon: FileSearch, value: `#${review.analysis_id}` },
    {
      icon: Filter,
      value: humanizeParserProfile(review.parsed?.parser_options?.profile, review.parsed?.parser_options?.profile),
    },
    {
      icon: FileSpreadsheet,
      value: isFinancialAnalysis
        ? `${financialAnalysis?.months?.length ?? 0} período(s)`
        : `${review.parsed?.parser_options?.checklist_sheet_names?.length || 1} aba(s)`,
    },
    { icon: Clock3, value: parseOriginLabel },
    {
      icon: Link2,
      value: `${reviewReferenceLinkCount} referência(s)`,
    },
    ...(review.stats?.parse_cache_saved_ms != null
      ? [{ icon: Sparkles, value: `Cache +${formatDuration(review.stats.parse_cache_saved_ms)}` }]
      : []),
  ];
  const reviewGuideCards = isFinancialAnalysis
    ? [
        {
          icon: Radar,
          title: "Leitura financeira",
          copy: "Períodos, entradas, despesas e resultado do demonstrativo.",
        },
        {
          icon: Waypoints,
          title: "Clientes e rastro",
          copy: "Clientes, contratos e lançamentos conciliados no recorte.",
        },
        {
          icon: History,
          title: "Prompt e histórico",
          copy: "Prompt, execuções e trilha da geração final.",
        },
      ]
    : [
        {
          icon: Radar,
          title: "Leitura estruturada",
          copy: "Recorte lido, alertas e itens elegíveis para composição.",
        },
        {
          icon: Layers3,
          title: "Camadas e evidências",
          copy: "Contexto do workbook, links e páginas rastreadas.",
        },
        {
          icon: History,
          title: "Prompt e histórico",
          copy: "Prompt auditável e execuções registradas.",
        },
      ];

  return (
    <motion.section
      ref={panelRef}
      key="review-panel"
      className="glass-panel review-panel"
      initial={REVIEW_PANEL_VARIANTS.initial}
      animate={REVIEW_PANEL_VARIANTS.animate}
      exit={REVIEW_PANEL_VARIANTS.exit}
      transition={REVIEW_PANEL_VARIANTS.transition}
    >
      <div className="panel-header">
        <div>
          <span className="eyebrow">Revisão auditável</span>
          <h2>Valide o contexto antes de exportar</h2>
        </div>
        <p className="panel-copy">
          {isFinancialAnalysis
            ? "Este painel separa resumo, DRE, clientes, contratos, lançamentos, evidências, prompt e histórico."
            : "Este painel separa alertas, camadas, itens, evidências, prompt e histórico."}
        </p>
      </div>

      <div className="workflow-grid workflow-grid-tight review-intro-grid">
        {reviewGuideCards.map((card) => (
          <GuideCard key={card.title} icon={card.icon} title={card.title} copy={card.copy} />
        ))}
      </div>

      <div className="review-fact-row">
        {reviewFactTags.map((fact) => (
          <Tag key={`${fact.value}`} icon={fact.icon}>
            {fact.value}
          </Tag>
        ))}
      </div>

      <div className="stats-grid stats-grid-compact review-stats-grid">
        {statsMetrics.map((metric) => (
          <MetricCard key={`${metric.label}-${metric.value}`} {...metric} />
        ))}
      </div>

      <div className="panel-navigator">
        <div>
          <span className="eyebrow eyebrow-soft">Navegação por contexto</span>
          <p className="navigator-copy">
            Use as abas para revisar cada camada sem abrir o painel inteiro de uma vez.
          </p>
        </div>
        <TabStrip tabs={reviewTabs} activeKey={activeTab} onChange={onTabChange} />
      </div>

      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeTab}
          className="tab-panel"
          initial={REVIEW_TAB_VARIANTS.initial}
          animate={REVIEW_TAB_VARIANTS.animate}
          exit={REVIEW_TAB_VARIANTS.exit}
          transition={REVIEW_TAB_VARIANTS.transition}
        >
          {activeTab === "overview" ? (
            <div className="review-stack">
              <article className="summary-card overview-summary-card">
                <div className="card-head">
                  <div>
                    <h3>{isFinancialAnalysis ? "Visão executiva do demonstrativo" : "Visão executiva da revisão"}</h3>
                    <p className="meta-line">
                      {isFinancialAnalysis
                        ? "Primeira leitura do recorte financeiro, com alertas e sinais que merecem checagem antes da exportação."
                        : "Primeira leitura do recorte estruturado, com alertas e sinais que merecem checagem antes da composição."}
                    </p>
                  </div>
                  <StatusPill tone={warningHeadline.tone} icon={overviewWarnings.length ? AlertTriangle : CheckCircle2}>
                    {warningHeadline.badge}
                  </StatusPill>
                </div>
                <div className="stats-grid stats-grid-compact overview-summary-metrics">
                  {overviewSummaryMetrics.map((metric) => (
                    <MetricCard key={`overview-${metric.label}-${metric.value}`} {...metric} />
                  ))}
                </div>
                <div className="overview-callout">
                  <strong>{warningHeadline.title}</strong>
                  <p>{warningHeadline.copy}</p>
                </div>
                <div className="overview-alert-pills">
                  <StatusPill tone="error" icon={AlertTriangle}>
                    Crítico {warningSummary.critical}
                  </StatusPill>
                  <StatusPill tone="warning" icon={AlertTriangle}>
                    Atenção {warningSummary.attention}
                  </StatusPill>
                  <StatusPill tone="neutral" icon={CheckCircle2}>
                    Informativo {warningSummary.info}
                  </StatusPill>
                </div>
                {overviewWarnings.length ? (
                  <>
                    <ul className="list-block overview-alert-list">
                      {visibleOverviewWarnings.map((warning, index) => (
                        <li key={`${warning}-${index}`}>{warning}</li>
                      ))}
                    </ul>
                    {remainingOverviewWarningCount > 0 ? (
                      <details className="trace-details overview-details">
                        <summary>{`Ver todos os alertas (${overviewWarnings.length})`}</summary>
                        <ul className="list-block overview-alert-list">
                          {overviewWarnings.map((warning, index) => (
                            <li key={`${warning}-detail-${index}`}>{warning}</li>
                          ))}
                        </ul>
                      </details>
                    ) : null}
                  </>
                ) : (
                  <EmptyBlock message="Nenhum alerta de leitura foi registrado nesta análise." />
                )}
              </article>

              <div className="card-grid overview-summary-grid">
                <article className="summary-card">
                  <div className="card-head">
                    <div>
                      <h3>Leitura estrutural</h3>
                      <p className="meta-line">
                        {review.stats?.parse_cache_hit
                          ? "Estrutura reidratada do cache seguro da conta antes do crawler."
                          : "Estrutura lida diretamente do envio antes do crawler."}
                      </p>
                    </div>
                    <StatusPill tone={review.stats?.parse_cache_hit ? "ready" : "neutral"} icon={Clock3}>
                      {parseOriginLabel}
                    </StatusPill>
                  </div>
                  <div className="overview-mini-metrics">
                    <FinancialRollupMetric label="Leitura" value={formatDuration(review.stats?.parse_duration_ms)} />
                    <FinancialRollupMetric
                      label="Crawler"
                      value={formatDuration(review.stats?.scrape_duration_ms)}
                    />
                    <FinancialRollupMetric
                      label="Páginas"
                      value={String(review.stats?.scraped_page_count ?? 0)}
                    />
                    <FinancialRollupMetric
                      label="Links"
                      value={String(review.stats?.scraped_link_count ?? 0)}
                    />
                    {review.stats?.parse_cache_saved_ms != null ? (
                      <FinancialRollupMetric
                        label="Cache"
                        value={`+${formatDuration(review.stats.parse_cache_saved_ms)}`}
                      />
                    ) : null}
                  </div>
                </article>

                <article className="summary-card">
                  <div className="card-head">
                    <div>
                      <h3>{isFinancialAnalysis ? "Escopo consolidado" : "Escopo e contexto"}</h3>
                      <p className="meta-line">
                        {reviewSheetNames.length
                          ? `${reviewSheetNames.length} aba(s), ${reviewLayerCount} camada(s) e ${selectedReferenceLinks.length} seed(s) no recorte.`
                          : "O parser não reportou abas específicas nesta análise."}
                      </p>
                    </div>
                    <StatusPill tone="neutral" icon={FileSpreadsheet}>
                      {isFinancialAnalysis ? "Recorte multi-período" : "Recorte multi-aba"}
                    </StatusPill>
                  </div>
                  <div className="overview-mini-metrics">
                    <FinancialRollupMetric label="Abas" value={String(reviewSheetNames.length)} />
                    <FinancialRollupMetric label="Camadas" value={String(reviewLayerCount)} />
                    <FinancialRollupMetric label="Seeds" value={String(selectedReferenceLinks.length)} />
                    <FinancialRollupMetric label="Referências" value={String(reviewReferenceLinkCount)} />
                  </div>
                  {reviewSheetNames.length || visibleLayerTypes.length || visibleReferenceLinks.length ? (
                    <details className="trace-details overview-details">
                      <summary>Ver composição do escopo</summary>
                      <div className="overview-detail-grid">
                        <div className="overview-group">
                          <strong>Abas</strong>
                          {visibleSheetNames.length ? (
                            <div className="trace-badges">
                              {visibleSheetNames.map((sheetName) => (
                                <Tag key={sheetName} icon={FileSpreadsheet}>
                                  {sheetName}
                                </Tag>
                              ))}
                              {remainingSheetCount > 0 ? <Tag icon={FileSpreadsheet}>+{remainingSheetCount}</Tag> : null}
                            </div>
                          ) : (
                            <EmptyBlock message="Nenhuma aba específica foi reportada pelo parser." />
                          )}
                        </div>
                        <div className="overview-group">
                          <strong>{isFinancialAnalysis ? "Camadas financeiras" : "Camadas"}</strong>
                          {visibleLayerTypes.length ? (
                            <div className="trace-badges">
                              {visibleLayerTypes.map((layer, index) => (
                                <Tag key={`${layer.layer_type}-${layer.sheet_name}-${index}`} icon={Layers3}>
                                  {humanizeLayerType(layer.layer_type)}
                                </Tag>
                              ))}
                              {remainingLayerCount > 0 ? <Tag icon={Layers3}>+{remainingLayerCount}</Tag> : null}
                            </div>
                          ) : (
                            <EmptyBlock message="Nenhuma camada complementar foi estruturada nesta análise." />
                          )}
                        </div>
                        <div className="overview-group">
                          <strong>Seeds do crawler</strong>
                          {visibleReferenceLinks.length ? (
                            <div className="trace-badges">
                              {visibleReferenceLinks.map((link, index) => (
                                <Tag key={`${link.url}-${index}`} icon={Link2}>
                                  {humanizeReferenceLinkKind(link.link_kind)} | {link.sheet_name}
                                </Tag>
                              ))}
                              {remainingReferenceLinkCount > 0 ? <Tag icon={Link2}>+{remainingReferenceLinkCount}</Tag> : null}
                            </div>
                          ) : (
                            <EmptyBlock message="Nenhuma seed adicional foi preparada para o crawler." />
                          )}
                        </div>
                      </div>
                    </details>
                  ) : (
                    <EmptyBlock message="Nenhum detalhe adicional de escopo foi estruturado nesta análise." />
                  )}
                </article>

                {isFinancialAnalysis && warehouseOverview?.snapshot_available ? (
                  <article className="summary-card">
                    <div className="card-head">
                      <div>
                        <h3>Perspectiva canônica do banco</h3>
                        <p className="meta-line">
                          Rankings lidos direto do warehouse, sem depender só do payload salvo da análise.
                        </p>
                      </div>
                      <StatusPill tone="ready" icon={Fingerprint}>
                        Warehouse
                      </StatusPill>
                    </div>
                    <div className="overview-mini-metrics">
                      <FinancialRollupMetric
                        label="Clientes"
                        value={String(warehouseOverview.client_count)}
                      />
                      <FinancialRollupMetric
                        label="Contratos"
                        value={String(warehouseOverview.contract_count)}
                      />
                      <FinancialRollupMetric
                        label="Lançamentos"
                        value={String(warehouseOverview.entry_count)}
                      />
                      <FinancialRollupMetric
                        label="Melhor período"
                        value={
                          warehouseTopPeriod
                            ? `${warehouseTopPeriod.period_label} | ${formatCompactCurrency(warehouseTopPeriod.net_result)}`
                            : "-"
                        }
                      />
                    </div>
                    <div className="trace-badges">
                      {warehouseTopClient ? (
                        <Tag icon={Waypoints}>
                          {`Cliente líder: ${compactEntityLabel(warehouseTopClient.client_name)} | ${formatCompactCurrency(warehouseTopClient.total_received_amount)}`}
                        </Tag>
                      ) : null}
                      {warehouseTopContract ? (
                        <Tag icon={Sparkles}>
                          {`Contrato líder: ${compactEntityLabel(warehouseTopContract.contract_label)} | ${formatCompactCurrency(warehouseTopContract.total_received_amount)}`}
                        </Tag>
                      ) : null}
                    </div>
                  </article>
                ) : null}
              </div>

              <ReviewSection
                title={isFinancialAnalysis ? "Resumo consolidado do demonstrativo" : "Resumo consolidado da análise"}
                subtitle={
                  isFinancialAnalysis
                    ? "Síntese textual do contexto financeiro consolidado antes da exportação."
                    : "Síntese textual do contexto consolidado antes da composição."
                }
              >
                <PreBlock text={review.summary || "Sem resumo consolidado."} />
              </ReviewSection>
            </div>
          ) : null}

          {activeTab === "dre" && isFinancialAnalysis ? (
            <div className="review-stack">
              {financialSnapshotMetrics.length ? (
                <div className="stats-grid stats-grid-compact">
                  {financialSnapshotMetrics.map((metric) => (
                    <MetricCard key={`financial-${metric.label}-${metric.value}`} {...metric} />
                  ))}
                </div>
              ) : null}

              <ReviewSection
                title="DRE consolidada"
                subtitle="Linhas consolidadas do demonstrativo a partir das abas e fontes financeiras lidas."
              >
                {financialAnalysis?.dre_lines?.length ? (
                  <div className="card-grid">
                    {financialAnalysis.dre_lines.map((line) => (
                      <FinancialLineCard key={line.key} line={line} />
                    ))}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhuma linha consolidada de DRE foi calculada." />
                )}
              </ReviewSection>

              <ReviewSection
                title="Recebimentos por cliente"
                subtitle={
                  topClient
                    ? `Mostra recebido, previsto e pendente por cliente. Líder atual: ${topClient.client_name}.`
                    : "Mostra recebido, previsto e pendente por cliente."
                }
              >
                {clientRollups.length ? (
                  <div className="card-grid financial-rollup-grid financial-rollup-grid-client">
                    {clientRollups.map((client) => (
                      <FinancialClientRollupCard key={client.client_name} client={client} />
                    ))}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhum agrupamento por cliente foi estruturado nesta análise." />
                )}
              </ReviewSection>

              <ReviewSection
                title="Recebimentos por contrato"
                subtitle={
                  topContract
                    ? `Mostra recebido, previsto e pendente por contrato. Líder atual: ${topContract.contract_label}.`
                    : "Mostra recebido, previsto e pendente por contrato."
                }
              >
                {contractRollups.length ? (
                  <div className="card-grid financial-rollup-grid financial-rollup-grid-contract">
                    {contractRollups.map((contract) => (
                      <FinancialContractRollupCard key={contract.contract_label} contract={contract} />
                    ))}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhum agrupamento por contrato foi estruturado nesta análise." />
                )}
              </ReviewSection>

              <ReviewSection
                title="Fechamento por período"
                subtitle="Resume receita base, custos, resultado e pendências em cada período lido pelo parser."
              >
                {financialAnalysis?.months?.length ? (
                  <div className="card-grid">
                    {financialAnalysis.months.map((month) => (
                      <FinancialMonthCard key={month.sheet_name} month={month} />
                    ))}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhum fechamento mensal foi consolidado." />
                )}
              </ReviewSection>
            </div>
          ) : null}

          {activeTab === "trace" && isFinancialAnalysis ? (
            <div className="review-stack">
              <ReviewSection
                title="Rastreabilidade financeira"
                subtitle="Consulte os lançamentos canônicos do warehouse e acompanhe a conciliação do recorte atual."
              >
                {financialTraceState.items.length ? (
                  <div className="trace-summary-grid">
                    <TraceSummaryCard
                      icon={CheckCircle2}
                      label="Confirmados"
                      count={traceSummary.matched.count}
                      amount={traceSummary.matched.amount}
                    />
                    <TraceSummaryCard
                      icon={AlertTriangle}
                      label="Prováveis"
                      count={traceSummary.probable.count}
                      amount={traceSummary.probable.amount}
                    />
                    <TraceSummaryCard
                      icon={Radar}
                      label="Sem pareamento"
                      count={traceSummary.unmatched.count}
                      amount={traceSummary.unmatched.amount}
                    />
                    <TraceSummaryCard
                      icon={Layers3}
                      label="Fora do escopo"
                      count={traceSummary.excluded.count}
                      amount={traceSummary.excluded.amount}
                    />
                    <TraceSummaryCard
                      icon={FileSpreadsheet}
                      label="Planilha no recorte"
                      count={traceSummary.workbook.count}
                      amount={traceSummary.workbook.amount}
                    />
                    <TraceSummaryCard
                      icon={FileText}
                      label="Extrato no recorte"
                      count={traceSummary.bank_statement.count}
                      amount={traceSummary.bank_statement.amount}
                    />
                    <TraceSummaryCard
                      icon={Fingerprint}
                      label="Com alias canônico"
                      count={traceSummary.alias_supported.count}
                      amount={traceSummary.alias_supported.amount}
                    />
                  </div>
                ) : null}

                <div className="trace-toolbar">
                  <p className="meta-line trace-toolbar-copy">
                    Mostrando os <strong>{financialTraceState.items.length}</strong> lançamentos mais relevantes do
                    recorte atual.
                    {hasTraceFilters ? ` ${activeTraceFilterCount} filtro(s) ativo(s).` : " Ajuste os filtros para focar em cliente, contrato ou período."}
                  </p>
                  {hasTraceFilters ? (
                    <button
                      type="button"
                      className="trace-toolbar-button"
                      onClick={() =>
                        setTraceFilters({
                          clientName: "",
                          contractLabel: "",
                          periodLabel: "",
                          entryType: "",
                          sourceKind: "",
                          reconciliationStatus: "",
                        })
                      }
                    >
                      Limpar filtros
                    </button>
                  ) : null}
                </div>

                <div className="trace-filter-grid trace-filter-grid-primary">
                  <SelectField
                    label="Cliente"
                    value={traceFilters.clientName}
                    onChange={(event) =>
                      setTraceFilters((current) => ({ ...current, clientName: event.target.value }))
                    }
                    options={traceClientOptions}
                  />
                  <SelectField
                    label="Contrato"
                    value={traceFilters.contractLabel}
                    onChange={(event) =>
                      setTraceFilters((current) => ({ ...current, contractLabel: event.target.value }))
                    }
                    options={traceContractOptions}
                  />
                  <SelectField
                    label="Período"
                    value={traceFilters.periodLabel}
                    onChange={(event) =>
                      setTraceFilters((current) => ({ ...current, periodLabel: event.target.value }))
                    }
                    options={tracePeriodOptions}
                  />
                </div>

                <details className="trace-advanced-filters">
                  <summary>
                    <Filter size={15} />
                    Filtros avançados
                  </summary>
                  <div className="trace-filter-grid">
                    <SelectField
                      label="Tipo"
                      value={traceFilters.entryType}
                      onChange={(event) =>
                        setTraceFilters((current) => ({ ...current, entryType: event.target.value }))
                      }
                      options={traceEntryTypeOptions}
                    />
                    <SelectField
                      label="Origem"
                      value={traceFilters.sourceKind}
                      onChange={(event) =>
                        setTraceFilters((current) => ({ ...current, sourceKind: event.target.value }))
                      }
                      options={traceSourceKindOptions}
                    />
                    <SelectField
                      label="Conciliação"
                      value={traceFilters.reconciliationStatus}
                      onChange={(event) =>
                        setTraceFilters((current) => ({
                          ...current,
                          reconciliationStatus: event.target.value,
                        }))
                      }
                      options={traceReconciliationStatusOptions}
                    />
                  </div>
                </details>

                {financialTraceState.loading ? (
                  <EmptyBlock message="Consultando lançamentos rastreáveis..." />
                ) : financialTraceState.error ? (
                  <EmptyBlock message={financialTraceState.error} tone="error" />
                ) : financialTraceState.items.length ? (
                  <div className="trace-entry-list">
                    {financialTraceState.items.map((entry) => {
                      const heading = entry.counterparty || entry.description;
                      const showDescription = normalizeTraceText(entry.description) !== normalizeTraceText(heading);
                      const shouldShowClientTag =
                        entry.canonical_client_name &&
                        normalizeTraceText(entry.canonical_client_name) !== normalizeTraceText(heading);
                      const hasExtendedTraceDetails = Boolean(
                        entry.entry_date ||
                          entry.due_date ||
                          entry.owner_label ||
                          entry.reconciliation_partner_period_label ||
                          entry.reconciliation_partner_description ||
                          entry.reconciliation_alias_label ||
                          entry.reconciliation_note ||
                          entry.notes ||
                          entry.status ||
                          entry.unit
                      );
                      return (
                        <article
                          key={`${entry.analysis_id}-${entry.position}`}
                          className={buildTraceEntryCardClass(entry)}
                        >
                          <div className="card-head">
                            <div>
                              <h3 title={heading}>{compactEntityLabel(heading, 52)}</h3>
                              <p className="meta-line">
                                {entry.period_label} | Aba {entry.sheet_name} | {humanizeFinancialEntryType(entry.entry_type)}
                              </p>
                            </div>
                            <StatusPill tone={(entry.amount ?? 0) >= 0 ? "ready" : "warning"} icon={Waypoints}>
                              {formatCurrency(entry.amount)}
                            </StatusPill>
                          </div>
                          {showDescription ? <p className="body-copy strong-copy">{entry.description}</p> : null}
                          <div className="trace-badges">
                            {entry.source_kind ? (
                              <Tag icon={entry.source_kind === "workbook" ? FileSpreadsheet : FileText}>
                                {humanizeFinancialSourceKind(entry.source_kind)}
                              </Tag>
                            ) : null}
                            <Tag icon={FileSearch}>{entry.section_title}</Tag>
                            {shouldShowClientTag ? <Tag icon={Waypoints}>{entry.canonical_client_name}</Tag> : null}
                            {entry.contract_label ? (
                              <Tag icon={Layers3}>
                                {compactEntityLabel(entry.contract_label, 34)}
                              </Tag>
                            ) : null}
                          </div>
                          <div className="trace-reconciliation-row">
                            {entry.reconciliation_status ? (
                              <StatusPill
                                tone={toneForFinancialReconciliationStatus(entry.reconciliation_status)}
                                icon={CheckCircle2}
                              >
                                {humanizeFinancialReconciliationStatus(entry.reconciliation_status)}
                              </StatusPill>
                            ) : null}
                            {entry.reconciliation_score != null ? (
                              <span className="meta-line">
                                Score {formatPercent(Math.max(0, Math.min(1, entry.reconciliation_score)))}
                              </span>
                            ) : null}
                            {entry.status ? <span className="meta-line">Status: {entry.status}</span> : null}
                            {entry.unit ? <span className="meta-line">Unidade: {entry.unit}</span> : null}
                            {entry.reconciliation_alias_label ? (
                              <span className="meta-line">Alias {entry.reconciliation_alias_label}</span>
                            ) : null}
                          </div>
                          {hasExtendedTraceDetails ? (
                            <details className="trace-details">
                              <summary>Ver contexto e conciliação</summary>
                              <ul className="detail-list trace-entry-meta">
                                {entry.entry_date ? <li>Data: {entry.entry_date}</li> : null}
                                {entry.due_date ? <li>Vencimento: {entry.due_date}</li> : null}
                                {entry.owner_label ? <li>Centro: {entry.owner_label}</li> : null}
                                {entry.reconciliation_partner_period_label ? (
                                  <li>Período pareado: {entry.reconciliation_partner_period_label}</li>
                                ) : null}
                                {entry.reconciliation_partner_description ? (
                                  <li>Contraparte pareada: {entry.reconciliation_partner_description}</li>
                                ) : null}
                                {entry.reconciliation_alias_label ? (
                                  <li>Alias canônico aplicado: {entry.reconciliation_alias_label}</li>
                                ) : null}
                                {entry.reconciliation_note ? <li>Conciliação: {entry.reconciliation_note}</li> : null}
                                {entry.notes ? <li>Notas: {entry.notes}</li> : null}
                              </ul>
                            </details>
                          ) : null}
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhum lançamento encontrou esse filtro. Ajuste cliente, contrato ou período para ampliar a busca." />
                )}
              </ReviewSection>
            </div>
          ) : null}

          {activeTab === "layers" ? (
            <ReviewSection
              title={isFinancialAnalysis ? "Camadas financeiras do workbook" : "Camadas abstratas do workbook"}
              subtitle={
                isFinancialAnalysis
                  ? "Cada card resume um fechamento, ponte de resultado ou estrutura de custos extraida da planilha."
                  : "Cada card resume uma aba ou matriz heterogênea transformada em contexto estruturado."
              }
            >
              {review.parsed?.context_layers?.length ? (
                <div className="card-grid">
                  {review.parsed.context_layers.map((layer, index) => (
                    <article key={`${layer.layer_type}-${layer.sheet_name}-${index}`} className="data-card">
                      <div className="card-head">
                        <div>
                          <h3>{layer.title}</h3>
                          <p className="meta-line">
                            {humanizeLayerType(layer.layer_type)} | Aba {layer.sheet_name}
                          </p>
                        </div>
                        <StatusPill tone="neutral" icon={Layers3}>
                          {layer.details?.length || 0} detalhe(s)
                        </StatusPill>
                      </div>
                      <p className="body-copy strong-copy">{layer.summary}</p>
                      {layer.details?.length ? (
                        <ul className="detail-list">
                          {layer.details.map((detail, detailIndex) => (
                            <li key={`${layer.title}-detail-${detailIndex}`}>{detail}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="meta-line">Sem detalhes adicionais estruturados nesta camada.</p>
                      )}
                      {layer.references?.length ? (
                        <ul className="detail-list">
                          {layer.references.map((reference, referenceIndex) => (
                            <li key={`${layer.title}-reference-${referenceIndex}`}>
                              {isLikelyUrl(reference) ? (
                                <a className="inline-link" href={reference} target="_blank" rel="noreferrer">
                                  {reference}
                                  <ArrowUpRight size={14} />
                                </a>
                              ) : (
                                reference
                              )}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyBlock message="Nenhuma camada abstrata foi estruturada para esta planilha." />
              )}
            </ReviewSection>
          ) : null}

          {activeTab === "items" ? (
            <ReviewSection
              title={isFinancialAnalysis ? "Lançamentos e seções estruturadas" : "Itens elegíveis para o relatório"}
              subtitle={
                isFinancialAnalysis
                  ? "Base principal usada pelo sistema para montar a DRE e o fechamento mensal."
                  : "Base principal usada pelo sistema para construir as seções do documento."
              }
            >
              {isFinancialAnalysis ? (
                financialAnalysis?.months?.length ? (
                  <div className="card-grid">
                    {financialAnalysis.months.map((month) => (
                      <article key={`month-${month.sheet_name}`} className="data-card">
                        <div className="card-head">
                          <div>
                            <h3>{month.period_label}</h3>
                            <p className="meta-line">{month.sections.length} seção(ões) estruturada(s)</p>
                          </div>
                          <StatusPill tone="neutral" icon={FileSearch}>
                            {month.sections.reduce((count, section) => count + (section.entry_count || 0), 0)} lanç.
                          </StatusPill>
                        </div>
                        <div className="trace-badges">
                          {month.sections.map((section) => (
                            <Tag
                              key={`${month.sheet_name}-${section.section_key}-${section.owner_label || "base"}`}
                              icon={FileSearch}
                            >
                              {section.title}: {formatCurrency(section.total_amount)}
                            </Tag>
                          ))}
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhum bloco financeiro foi estruturado nesta análise." />
                )
              ) : review.parsed?.itens_processados?.length ? (
                <div className="card-grid">
                  {review.parsed.itens_processados.map((item) => (
                    <article key={`${item.item_codigo}-${item.linha_referencia}`} className="data-card">
                      <div className="card-head">
                        <div>
                          <h3>{item.item_codigo}</h3>
                          <p className="meta-line">
                            {humanizeSource(item.fonte)} | Linha {item.linha_referencia}
                            {item.ano_referencia ? ` | Ano ${item.ano_referencia}` : ""}
                          </p>
                        </div>
                        <StatusPill
                          tone={humanizeStatusTone(item.status)}
                          icon={item.status === "Sim" ? CheckCircle2 : AlertTriangle}
                        >
                          {item.status}
                        </StatusPill>
                      </div>
                      <p className="body-copy strong-copy">{item.descricao_item}</p>
                      {item.observacao ? <p className="body-copy">{item.observacao}</p> : null}
                      {item.detalhes?.length ? (
                        <ul className="detail-list">
                          {item.detalhes.map((detail, index) => (
                            <li key={`${item.item_codigo}-detail-${index}`}>
                              {detail.descricao}: {detail.status}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyBlock message="Nenhum item elegível apareceu no recorte atual. Amplie perfil, grupos ou status se precisar." />
              )}
            </ReviewSection>
          ) : null}

          {activeTab === "crawler" ? (
            <div className="review-stack">
              <ReviewSection
                title="Seeds usados pelo crawler"
                subtitle="Origem das URLs estruturadas e referenciais que entraram na fila automática."
              >
                {review.parsed?.reference_links?.length ? (
                  <div className="card-grid">
                    {review.parsed.reference_links.map((link, index) => (
                      <article key={`${link.url}-${index}`} className="data-card">
                        <div className="card-head">
                          <div>
                            <h3>{link.label || link.url}</h3>
                            <p className="meta-line">
                              {humanizeReferenceLinkKind(link.link_kind)} | Aba {link.sheet_name}
                              {link.cell_reference ? ` | Célula ${link.cell_reference}` : ""}
                            </p>
                          </div>
                          <StatusPill
                            tone={link.selected_for_crawl ? "ready" : link.crawlable ? "warning" : "neutral"}
                            icon={Link2}
                          >
                            {link.selected_for_crawl
                              ? "No scan automático"
                              : link.crawlable
                                ? "Fora do limite atual"
                                : "Não navegável"}
                          </StatusPill>
                        </div>
                        <a className="inline-link" href={link.url} target="_blank" rel="noreferrer">
                          {link.url}
                          <ArrowUpRight size={14} />
                        </a>
                        <p className="meta-line">Fonte sugerida: {humanizeSource(link.source_hint)}</p>
                        {link.context ? <p className="body-copy">{link.context}</p> : null}
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhuma URL adicional foi estruturada a partir do workbook nesta análise." />
                )}
              </ReviewSection>

              <ReviewSection
                title="Páginas e evidências rastreadas"
                subtitle="Apoio contextual coletado pelo crawler para enriquecer a leitura."
              >
                {review.parsed?.scraped_pages?.length ? (
                  <div className="card-grid">
                    {review.parsed.scraped_pages.map((page, index) => (
                      <article key={`${page.final_url}-${index}`} className="data-card">
                        <div className="card-head">
                          <div>
                            <h3>{page.page_title || "Página sem título"}</h3>
                            <p className="meta-line">{humanizeSource(page.fonte)}</p>
                          </div>
                          <StatusPill tone="neutral" icon={Globe2}>
                            {page.links?.length ? `${page.links.length} link(s)` : "0 link"}
                          </StatusPill>
                        </div>
                        <p className="body-copy">{page.summary}</p>
                        <p className="meta-line">
                          {page.final_url} | Profundidade: {page.discovery_depth ?? 0}
                          {page.discovered_from_label ? ` | Via: ${page.discovered_from_label}` : ""}
                          {typeof page.page_score === "number" && page.page_score > 0
                            ? ` | Pontuação: ${page.page_score}`
                            : ""}
                        </p>
                        {page.links?.slice(0, 4).length ? (
                          <ul className="detail-list">
                            {page.links.slice(0, 4).map((link, linkIndex) => (
                              <li key={`${page.final_url}-link-${linkIndex}`}>
                                {humanizeCategory(link.category)}: {link.label || link.url}
                                {typeof link.score === "number" ? ` | Pontuação ${link.score}` : ""}
                                {link.evidence_summary ? ` | ${link.evidence_summary}` : ""}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </article>
                    ))}
                  </div>
                ) : (
                  <EmptyBlock message="Nenhuma página foi rastreada nesta análise. O relatório seguirá apenas com checklist e metadados." />
                )}
              </ReviewSection>
            </div>
          ) : null}

          {activeTab === "prompt" ? (
            <div className="review-stack">
              <ReviewSection
                title={isFinancialAnalysis ? "Prévia do prompt financeiro" : "Prévia do prompt de composição"}
                subtitle={
                  isFinancialAnalysis
                    ? "Permite auditar as instruções usadas para gerar a leitura executiva e a DRE."
                    : "Permite auditar as instruções repassadas para a geração do texto."
                }
              >
                <div className="stats-grid stats-grid-compact">
                  <MetricCard
                    icon={FileSearch}
                    label="Perfil do parser"
                    value={humanizeParserProfile(review.parsed?.parser_options?.profile, "Automático")}
                  />
                  <MetricCard
                    icon={Layers3}
                    label="Abas no recorte"
                    value={summarizeStoredSheetSelection(reviewSheetNames, review.parsed?.parser_options)}
                  />
                  <MetricCard
                    icon={Radar}
                    label={isFinancialAnalysis ? "Lançamentos no contexto" : "Itens no contexto"}
                    value={String(reviewItemCount)}
                  />
                  <MetricCard
                    icon={Waypoints}
                    label={isFinancialAnalysis ? "Camadas financeiras" : "Camadas estruturadas"}
                    value={String(reviewLayerCount)}
                  />
                  <MetricCard
                    icon={FileText}
                    label="Tamanho da prévia"
                    value={promptPreviewLength ? `${promptPreviewLength} caracteres` : "-"}
                  />
                </div>

                <article className="summary-card generation-trace-card">
                  <div className="card-head">
                    <div>
                      <h3>Configuração ativa da geração</h3>
                      <p className="meta-line">Referência rápida do modo de composição que será aplicado ao exportar.</p>
                    </div>
                    <StatusPill tone="neutral" icon={Sparkles}>
                      Composição atual
                    </StatusPill>
                  </div>
                  <div className="trace-badges">
                    <Tag icon={Sparkles}>{humanizeGenerationMode(formState.generationMode)}</Tag>
                    <Tag icon={FileText}>{(formState.outputFormat || "docx").toUpperCase()}</Tag>
                    <Tag icon={Bot}>{describeLocalModelSelection(formState.localModel, recommendedLocalModel)}</Tag>
                    {review.parsed?.orgao ? <Tag icon={FileSearch}>{review.parsed.orgao}</Tag> : null}
                    {review.parsed?.periodo_analise ? <Tag icon={Clock3}>{review.parsed.periodo_analise}</Tag> : null}
                  </div>
                  <div className="generation-summary-grid">
                    <div className="generation-summary-item">
                      <span>Modo de geração</span>
                      <strong>{humanizeGenerationMode(formState.generationMode)}</strong>
                    </div>
                    <div className="generation-summary-item">
                      <span>Formato de saída</span>
                      <strong>{(formState.outputFormat || "docx").toUpperCase()}</strong>
                    </div>
                    <div className="generation-summary-item">
                      <span>Modelo local</span>
                      <strong>{describeLocalModelSelection(formState.localModel, recommendedLocalModel)}</strong>
                    </div>
                    <div className="generation-summary-item">
                      <span>{isFinancialAnalysis ? "Escopo financeiro" : "Escopo da leitura"}</span>
                      <strong>
                        {isFinancialAnalysis
                          ? `${clientRollups.length} cliente(s) | ${contractRollups.length} contrato(s)`
                          : `${reviewItemCount} item(ns) | ${reviewLayerCount} camada(s)`}
                      </strong>
                    </div>
                  </div>
                </article>

                {isFinancialAnalysis && financialAnalysis ? (
                  <article className="summary-card generation-trace-card">
                    <div className="card-head">
                      <div>
                        <h3>Fatos financeiros que entram no prompt</h3>
                        <p className="meta-line">Resumo curto da base estruturada que sustenta a composição.</p>
                      </div>
                      <StatusPill tone="neutral" icon={FileSpreadsheet}>
                        Base financeira
                      </StatusPill>
                    </div>
                    <div className="generation-summary-grid">
                      <div className="generation-summary-item">
                        <span>Períodos</span>
                        <strong>{financialAnalysis.months.length}</strong>
                      </div>
                      <div className="generation-summary-item">
                        <span>Clientes</span>
                        <strong>{clientRollups.length}</strong>
                      </div>
                      <div className="generation-summary-item">
                        <span>Contratos</span>
                        <strong>{contractRollups.length}</strong>
                      </div>
                      <div className="generation-summary-item">
                        <span>Resultado consolidado</span>
                        <strong>{formatCompactCurrency(summaryNetResult)}</strong>
                      </div>
                    </div>
                  </article>
                ) : null}

                <details className="trace-details">
                  <summary>Ver prévia completa do prompt {promptPreviewLength ? `(${promptPreviewLength} caracteres)` : ""}</summary>
                  <PreBlock text={review.prompt_preview || "Sem prompt disponível."} />
                </details>
              </ReviewSection>
            </div>
          ) : null}

          {activeTab === "history" ? (
            <ReviewSection
              title="Histórico de geração e auditoria"
              subtitle="Rastro completo de provedor, modelo, fallback, tempo e payload salvo."
            >
              {generationHistoryState.loading ? (
                <EmptyBlock message="Consultando execuções registradas..." />
              ) : generationHistoryState.error ? (
                <EmptyBlock message={generationHistoryState.error} tone="error" />
              ) : generationHistoryState.items.length ? (
                <>
                  <div className="stats-grid stats-grid-compact">
                    <MetricCard icon={History} label="Execuções salvas" value={String(generationHistoryState.items.length)} />
                    <MetricCard
                      icon={Bot}
                      label="Último provedor"
                      value={latestGeneration ? humanizeProvider(latestGeneration.provider) : "-"}
                    />
                    <MetricCard
                      icon={Sparkles}
                      label="Modo executado"
                      value={latestGeneration ? humanizeGenerationMode(latestGeneration.used_mode) : "-"}
                    />
                    <MetricCard
                      icon={Clock3}
                      label="Último tempo"
                      value={latestGeneration?.duration_ms != null ? formatDuration(latestGeneration.duration_ms) : "-"}
                    />
                    <MetricCard
                      icon={AlertTriangle}
                      label="Fallbacks registrados"
                      value={String(generationFallbackCount)}
                    />
                  </div>
                  <div className="trace-stack">
                    {generationHistoryState.items.map((trace, index) => (
                      <TraceCard
                        key={trace.id || `trace-${index}`}
                        trace={trace}
                        isHighlighted={
                          highlightGenerationId != null
                            ? String(trace.id) === String(highlightGenerationId)
                            : index === 0
                        }
                      />
                    ))}
                  </div>
                </>
              ) : (
                <EmptyBlock message="Nenhuma execução foi registrada ainda para esta análise." />
              )}
            </ReviewSection>
          ) : null}
        </motion.div>
      </AnimatePresence>
    </motion.section>
  );
}
