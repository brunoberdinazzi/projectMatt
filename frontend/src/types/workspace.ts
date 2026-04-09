import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export type StatusTone = "idle" | "ready" | "error" | "warning" | "neutral";
export type OutputFormat = "docx" | "pdf";
export type GenerationMode = "auto" | "local" | "ai" | "rules";
export type LayoutProfile = "" | "profile_a" | "profile_b";

export interface AppFormState {
  file: File | null;
  files: File[];
  templateFile: File | null;
  outputFormat: OutputFormat;
  generationMode: GenerationMode;
  localModel: string;
  parserProfile: string;
  allowedGroups: string;
  allowedStatus: string;
  checklistSheetName: string;
  periodoAnalise: string;
  numeroRelatorio: string;
  solicitacao: string;
  requesterArea: string;
  referencia: string;
  cidadeEmissao: string;
  dataEmissao: string;
  periodoColeta: string;
  relatorioContabilReferencia: string;
  equipeTecnica: string;
  orgao: string;
  layoutProfile: LayoutProfile;
  scrapeUrl: string;
  scrapeMaxLinks: string;
  scrapeDepth: string;
  scrapeMaxPages: string;
}

export interface SelectOption<T = string> {
  value: T;
  label: string;
}

export interface LoginForm {
  email: string;
  password: string;
}

export interface RegisterForm {
  fullName: string;
  email: string;
  password: string;
}

export interface ForgotPasswordForm {
  email: string;
}

export interface ResetPasswordForm {
  token: string;
  newPassword: string;
  confirmPassword: string;
}

export interface AsyncItemsState<T> {
  loading: boolean;
  error: string;
  items: T[];
}

export interface AsyncDataState<T> {
  loading: boolean;
  error: string;
  data: T | null;
}

export interface ParserProfileDefinition {
  key: string;
  label: string;
  description: string;
  allowed_groups?: string[];
  allowed_status?: string[];
}

export interface StoredParserOptions {
  checklist_sheet_names?: string[];
  checklist_sheet_name?: string;
}

export interface WorkspaceMetric {
  label: string;
  value: string;
  icon: LucideIcon;
}

export interface StatusFeedback {
  message: string;
  error: boolean;
}

export interface AuthPasswordForgotResponse {
  ok: boolean;
  message?: string | null;
  reset_token?: string | null;
  expires_at?: string | null;
}

export interface ParserDetectionResponse {
  requested_profile: string;
  resolved_profile: string;
  resolved_label: string;
  resolved_description?: string | null;
  message?: string | null;
}

export interface ParserDetectionState {
  loading: boolean;
  error: string;
  data: ParserDetectionResponse | null;
}

export interface ParserOptions {
  profile?: string;
  allowed_groups?: string[];
  allowed_status?: string[];
  checklist_sheet_name?: string;
  checklist_sheet_names?: string[];
}

export interface ChecklistDetail {
  descricao: string;
  status: string;
}

export interface ChecklistItem {
  grupo: string;
  item_codigo: string;
  linha_referencia: number;
  ano_referencia?: string | null;
  status: string;
  fonte: string;
  descricao_item: string;
  observacao?: string | null;
  detalhes?: ChecklistDetail[];
}

export interface WorkbookContextLayer {
  layer_type: string;
  sheet_name: string;
  title: string;
  summary: string;
  details?: string[];
  references?: string[];
}

export interface WorkbookReferenceLink {
  url: string;
  sheet_name: string;
  cell_reference?: string | null;
  label?: string | null;
  context?: string | null;
  source_hint: string;
  link_kind: string;
  crawlable: boolean;
  selected_for_crawl: boolean;
}

export interface ScrapedLink {
  label: string;
  url: string;
  category: string;
  destination_type: string;
  context?: string | null;
  section?: string | null;
  is_internal?: boolean;
  score?: number;
  matched_terms?: string[];
  evidence_summary?: string | null;
}

export interface ScrapedPageRecord {
  fonte: string;
  requested_url: string;
  final_url: string;
  page_title?: string | null;
  summary: string;
  links?: ScrapedLink[];
  discovery_depth?: number;
  page_score?: number;
  discovered_from_url?: string | null;
  discovered_from_label?: string | null;
  warnings?: string[];
}

export interface FinancialSectionSnapshot {
  section_key: string;
  title: string;
  owner_label?: string | null;
  total_amount?: number | null;
  entry_count: number;
}

export interface FinancialPeriodSummary {
  sheet_name: string;
  period_label: string;
  gross_revenue_total?: number | null;
  receivables_total?: number | null;
  other_income_total?: number | null;
  taxes_total?: number | null;
  personnel_total?: number | null;
  fixed_costs_total?: number | null;
  operating_costs_total?: number | null;
  global_expenses_total?: number | null;
  net_result?: number | null;
  closing_total?: number | null;
  pending_entry_count: number;
  sections: FinancialSectionSnapshot[];
}

export interface FinancialStatementLine {
  key: string;
  label: string;
  amount: number;
  line_type: string;
  share_of_gross_revenue?: number | null;
}

export interface FinancialClientRollup {
  canonical_client_id?: number | null;
  canonical_client_name?: string | null;
  client_name: string;
  total_received_amount: number;
  total_expected_amount: number;
  total_pending_amount: number;
  contract_count: number;
  months_covered?: string[];
  contract_labels?: string[];
  reconciliation_matched_count?: number;
  reconciliation_probable_count?: number;
  reconciliation_unmatched_count?: number;
  reconciliation_excluded_count?: number;
  reconciliation_matched_amount?: number;
  reconciliation_probable_amount?: number;
  reconciliation_unmatched_amount?: number;
  reconciliation_excluded_amount?: number;
  reconciliation_alias_supported_count?: number;
  reconciliation_alias_supported_amount?: number;
  reconciliation_coverage_ratio?: number | null;
}

export interface FinancialContractRollup {
  canonical_contract_id?: number | null;
  canonical_contract_name?: string | null;
  contract_label: string;
  client_name?: string | null;
  unit?: string | null;
  contract_start_date?: string | null;
  contract_end_date?: string | null;
  latest_status?: string | null;
  total_received_amount: number;
  total_expected_amount: number;
  total_pending_amount: number;
  entry_count: number;
  months_covered?: string[];
  source_sheet_names?: string[];
  reconciliation_matched_count?: number;
  reconciliation_probable_count?: number;
  reconciliation_unmatched_count?: number;
  reconciliation_excluded_count?: number;
  reconciliation_matched_amount?: number;
  reconciliation_probable_amount?: number;
  reconciliation_unmatched_amount?: number;
  reconciliation_excluded_amount?: number;
  reconciliation_alias_supported_count?: number;
  reconciliation_alias_supported_amount?: number;
  reconciliation_coverage_ratio?: number | null;
}

export interface FinancialTraceEntry {
  analysis_id: number;
  position: number;
  canonical_client_id?: number | null;
  canonical_client_name?: string | null;
  canonical_contract_id?: number | null;
  canonical_contract_name?: string | null;
  period_label: string;
  sheet_name: string;
  section_key: string;
  section_title: string;
  owner_label?: string | null;
  entry_type: string;
  description: string;
  amount?: number | null;
  status?: string | null;
  entry_date?: string | null;
  due_date?: string | null;
  counterparty?: string | null;
  unit?: string | null;
  notes?: string | null;
  contract_label?: string | null;
  contract_start_date?: string | null;
  contract_end_date?: string | null;
  source_kind?: "workbook" | "bank_statement" | null;
  reconciliation_status?: "matched" | "probable" | "unmatched" | "excluded" | null;
  reconciliation_score?: number | null;
  reconciliation_partner_period_label?: string | null;
  reconciliation_partner_description?: string | null;
  reconciliation_alias_label?: string | null;
  reconciliation_note?: string | null;
  tags?: string[];
}

export interface FinancialAnalysisResult {
  workbook_kind: string;
  fiscal_year?: number | null;
  entity_name?: string | null;
  source_workbook_count?: number;
  source_workbook_names?: string[];
  months: FinancialPeriodSummary[];
  dre_lines: FinancialStatementLine[];
  client_rollups?: FinancialClientRollup[];
  contract_rollups?: FinancialContractRollup[];
  summary_notes?: string[];
  detected_entities?: string[];
  entry_count: number;
}

export interface FinancialWarehouseTopClient {
  canonical_client_id?: number | null;
  client_name: string;
  total_received_amount: number;
  total_expected_amount: number;
  total_pending_amount: number;
  contract_count: number;
}

export interface FinancialWarehouseTopContract {
  canonical_contract_id?: number | null;
  contract_label: string;
  client_name?: string | null;
  total_received_amount: number;
  total_expected_amount: number;
  total_pending_amount: number;
  entry_count: number;
}

export interface FinancialWarehouseTopPeriod {
  period_label: string;
  net_result: number;
  gross_revenue_total: number;
  global_expenses_total: number;
  pending_entry_count: number;
}

export interface FinancialWarehouseOverview {
  analysis_id: number;
  snapshot_available: boolean;
  entry_count: number;
  client_count: number;
  contract_count: number;
  period_count: number;
  top_clients: FinancialWarehouseTopClient[];
  top_contracts: FinancialWarehouseTopContract[];
  top_periods: FinancialWarehouseTopPeriod[];
}

export interface ChecklistParseResult {
  analysis_id?: number | null;
  orgao?: string | null;
  tipo_orgao?: string | null;
  periodo_analise?: string | null;
  numero_relatorio?: string | null;
  solicitacao?: string | null;
  promotoria?: string | null;
  referencia?: string | null;
  cidade_emissao?: string | null;
  data_emissao?: string | null;
  periodo_coleta?: string | null;
  relatorio_contabil_referencia?: string | null;
  equipe_tecnica?: string | null;
  parser_options?: ParserOptions;
  itens_processados?: ChecklistItem[];
  context_layers?: WorkbookContextLayer[];
  reference_links?: WorkbookReferenceLink[];
  financial_analysis?: FinancialAnalysisResult | null;
  warehouse_overview?: FinancialWarehouseOverview | null;
  scraped_pages?: ScrapedPageRecord[];
  warnings?: string[];
}

export interface AnalysisReviewStats {
  extracted_item_count: number;
  warning_count: number;
  scraped_page_count: number;
  scraped_link_count: number;
  parse_duration_ms?: number | null;
  scrape_duration_ms?: number | null;
  parse_cache_hit: boolean;
  parse_cache_saved_ms?: number | null;
}

export interface AnalysisReviewResponse {
  analysis_id: number;
  parsed: ChecklistParseResult;
  summary: string;
  prompt_preview: string;
  stats: AnalysisReviewStats;
}

export interface GenerationTraceItem {
  id?: number | null;
  session_public_id?: string | null;
  requested_mode: string;
  used_mode: string;
  provider: string;
  model_name?: string | null;
  output_format: string;
  prompt_snapshot?: string | null;
  raw_response?: string | null;
  fallback_reason?: string | null;
  duration_ms?: number | null;
  created_at?: string | null;
}

export interface ScrapePageResult {
  requested_url: string;
  final_url: string;
  page_title?: string | null;
  summary: string;
  links?: ScrapedLink[];
  discovered_pages?: ScrapedPageRecord[];
  warnings?: string[];
  processing_time_ms?: number | null;
}

export interface StoredAnalysisListItem {
  analysis_id: number;
  created_at?: string | null;
  source_filename?: string | null;
  orgao?: string | null;
  tipo_orgao?: string | null;
  periodo_analise?: string | null;
  parser_profile?: string | null;
  checklist_sheet_names?: string[];
  extracted_item_count: number;
  scraped_page_count: number;
  generation_count: number;
  last_generation_at?: string | null;
}

export interface OllamaLoadedModel {
  name: string;
  size_vram?: number | null;
  context_length?: number | null;
  expires_at?: string | null;
}

export interface OllamaStatusResponse {
  available: boolean;
  latency_ms?: number | null;
  base_url?: string | null;
  recommended_model?: string | null;
  active_model?: string | null;
  installed_model_count?: number;
  loaded_model_count?: number;
  loaded_models?: OllamaLoadedModel[];
  message?: string | null;
}

export interface OllamaModelsResponse {
  models?: string[];
  recommended_model?: string | null;
}

export interface AuthUser {
  id: number;
  full_name: string;
  email: string;
  created_at?: string | null;
}

export interface AuthSessionInfo {
  session_id: string;
  created_at?: string | null;
  expires_at?: string | null;
}

export interface AuthSessionResponse {
  user: AuthUser | null;
  session: AuthSessionInfo | null;
}

export type FinancialAliasKind = "client" | "contract";

export interface FinancialAliasItem {
  kind: FinancialAliasKind;
  entity_id: number;
  canonical_name: string;
  aliases: string[];
  canonical_client_id?: number | null;
  canonical_client_name?: string | null;
  unit?: string | null;
  contract_start_date?: string | null;
  contract_end_date?: string | null;
  first_period_label?: string | null;
  last_period_label?: string | null;
  updated_at?: string | null;
}

export interface FinancialAliasCatalogResponse {
  clients: FinancialAliasItem[];
  contracts: FinancialAliasItem[];
}

export interface SessionState {
  loading: boolean;
  user: AuthUser | null;
  session: AuthSessionInfo | null;
  error: string;
}

export interface AccountProfileForm {
  fullName: string;
  email: string;
}

export interface AccountPasswordForm {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export type AccountProfileField = keyof AccountProfileForm;
export type AccountPasswordField = keyof AccountPasswordForm;

export interface TabDescriptor {
  key: string;
  label: string;
  icon: LucideIcon;
  count?: number;
}

export type ActiveWorkspaceTab = "composer" | "review" | "crawler";
export type ActiveReviewTab = "overview" | "dre" | "trace" | "layers" | "items" | "crawler" | "prompt" | "history";
export type ActiveUtilityModal = "status" | "analyses" | "aliases" | "local-ai" | "account";

export type ModalFrameSize = "default" | "wide" | "narrow";
