import { motion } from "framer-motion";
import type { FormEventHandler } from "react";
import {
  Activity,
  Bot,
  CheckCircle2,
  FileSearch,
  Fingerprint,
  Filter,
  Globe2,
  History,
  Layers3,
  Plus,
  ShieldCheck,
  Sparkles,
  UserRoundCog,
  X,
} from "lucide-react";

import {
  formatDuration,
  formatGenerationDate,
  humanizeParserProfile,
} from "../lib/app-utils";
import type {
  AccountPasswordField,
  AccountPasswordForm,
  AccountProfileField,
  AccountProfileForm,
  FinancialAliasCatalogResponse,
  FinancialAliasItem,
  FinancialAliasKind,
  ActiveUtilityModal,
  AnalysisReviewResponse,
  AsyncDataState,
  AsyncItemsState,
  AuthSessionInfo,
  OllamaStatusResponse,
  ParserProfileDefinition,
  StatusFeedback,
  StatusTone,
  StoredAnalysisListItem,
  TabDescriptor,
} from "../types/workspace";
import {
  EmptyBlock,
  ModalFrame,
  PanelTitle,
  StatusBlock,
  StatusPill,
  TabStrip,
  Tag,
  TextField,
} from "./ui";

const PANEL_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const PANEL_VARIANTS = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: PANEL_EASE },
  },
};

interface WorkspaceHubProps {
  activeTab: string;
  onTabChange: (key: string) => void;
  tabs: TabDescriptor[];
  primaryStatusTone: StatusTone;
  reviewReady: boolean;
  reviewStale: boolean;
  reviewData: AnalysisReviewResponse | null;
  recentAnalysesCount: number;
  localAiAvailable: boolean;
  onOpenModal: (modal: ActiveUtilityModal) => void;
}

export function WorkspaceHub({
  activeTab,
  onTabChange,
  tabs,
  primaryStatusTone,
  reviewReady,
  reviewStale,
  reviewData,
  recentAnalysesCount,
  localAiAvailable,
  onOpenModal,
}: WorkspaceHubProps) {
  return (
    <motion.section className="glass-panel workspace-hub" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
      <div className="workspace-hub-top">
        <div>
          <span className="eyebrow">Workspace organizado</span>
          <h2>Escolha a etapa e abra o apoio quando precisar</h2>
        </div>
        <p className="panel-copy">
          As abas organizam configuração, revisão e crawler. O apoio rápido fica nos modais.
        </p>
      </div>

      <div className="workspace-hub-toolbar">
        <div className="workspace-hub-tabs">
          <TabStrip tabs={tabs} activeKey={activeTab} onChange={onTabChange} />
        </div>

        <div className="workspace-hub-meta">
          <StatusPill tone={primaryStatusTone} icon={primaryStatusTone === "error" ? Activity : CheckCircle2}>
            {reviewStale ? "Revisão desatualizada" : reviewReady ? "Revisão pronta" : "Aguardando revisão"}
          </StatusPill>
          {reviewData?.analysis_id ? <Tag icon={FileSearch}>#{reviewData.analysis_id}</Tag> : null}
          <Tag icon={History}>{recentAnalysesCount} recente(s)</Tag>
          <Tag icon={Bot}>{localAiAvailable ? "IA local ok" : "IA local offline"}</Tag>
        </div>
      </div>

      <div className="workspace-utility-grid">
        <button className="workspace-utility-button" type="button" onClick={() => onOpenModal("status")}>
          <span className="icon-badge icon-badge-soft">
            <ShieldCheck size={16} />
          </span>
          <div>
            <strong>Fluxo e status</strong>
            <span>Gate, perfil e estado atual.</span>
          </div>
        </button>

        <button className="workspace-utility-button" type="button" onClick={() => onOpenModal("analyses")}>
          <span className="icon-badge icon-badge-soft">
            <History size={16} />
          </span>
          <div>
            <strong>Análises</strong>
            <span>Reabra revisões sem reenviar arquivos.</span>
          </div>
        </button>

        <button className="workspace-utility-button" type="button" onClick={() => onOpenModal("aliases")}>
          <span className="icon-badge icon-badge-soft">
            <Fingerprint size={16} />
          </span>
          <div>
            <strong>Aliases</strong>
            <span>Vincule nomes bancários a clientes e contratos.</span>
          </div>
        </button>

        <button className="workspace-utility-button" type="button" onClick={() => onOpenModal("local-ai")}>
          <span className="icon-badge icon-badge-soft">
            <Bot size={16} />
          </span>
          <div>
            <strong>IA local</strong>
            <span>Veja o Ollama e a saúde local.</span>
          </div>
        </button>

        <button className="workspace-utility-button" type="button" onClick={() => onOpenModal("account")}>
          <span className="icon-badge icon-badge-soft">
            <UserRoundCog size={16} />
          </span>
          <div>
            <strong>Conta</strong>
            <span>Atualize nome, e-mail e senha.</span>
          </div>
        </button>
      </div>
    </motion.section>
  );
}

interface WorkspaceUtilityModalProps {
  activeModal: ActiveUtilityModal | null;
  onClose: () => void;
  primaryStatusTone: StatusTone;
  status: StatusFeedback;
  selectedParserProfile: ParserProfileDefinition | null;
  reviewData: AnalysisReviewResponse | null;
  recentAnalysesState: AsyncItemsState<StoredAnalysisListItem>;
  isLoadingStoredAnalysis: boolean;
  savedAnalysisId: string;
  setSavedAnalysisId: (value: string) => void;
  onStoredAnalysisSubmit: FormEventHandler<HTMLFormElement>;
  onStoredAnalysisClick: (analysisId: number) => void | Promise<void>;
  ollamaStatusState: AsyncDataState<OllamaStatusResponse>;
  recommendedLocalModel: string;
  onRefreshLocalAi: () => void;
  sessionInfo: AuthSessionInfo | null;
  accountProfileForm: AccountProfileForm;
  onAccountProfileFieldChange: (field: AccountProfileField, value: string) => void;
  onAccountProfileSubmit: FormEventHandler<HTMLFormElement>;
  isSavingAccountProfile: boolean;
  accountProfileFeedback: StatusFeedback;
  accountPasswordForm: AccountPasswordForm;
  onAccountPasswordFieldChange: (field: AccountPasswordField, value: string) => void;
  onAccountPasswordSubmit: FormEventHandler<HTMLFormElement>;
  isSavingAccountPassword: boolean;
  accountPasswordFeedback: StatusFeedback;
  financialAliasesState: AsyncDataState<FinancialAliasCatalogResponse>;
  aliasDrafts: Record<string, string>;
  aliasBusyKey: string | null;
  aliasFeedback: StatusFeedback;
  onAliasDraftChange: (kind: FinancialAliasKind, entityId: number, value: string) => void;
  onAddFinancialAlias: (kind: FinancialAliasKind, entityId: number) => void | Promise<void>;
  onRemoveFinancialAlias: (kind: FinancialAliasKind, entityId: number, alias: string) => void | Promise<void>;
  onRefreshFinancialAliases: () => void;
}

interface FinancialAliasSectionProps {
  title: string;
  kicker: string;
  emptyMessage: string;
  kind: FinancialAliasKind;
  items: FinancialAliasItem[];
  aliasDrafts: Record<string, string>;
  aliasBusyKey: string | null;
  onAliasDraftChange: (kind: FinancialAliasKind, entityId: number, value: string) => void;
  onAddFinancialAlias: (kind: FinancialAliasKind, entityId: number) => void | Promise<void>;
  onRemoveFinancialAlias: (kind: FinancialAliasKind, entityId: number, alias: string) => void | Promise<void>;
}

function FinancialAliasSection({
  title,
  kicker,
  emptyMessage,
  kind,
  items,
  aliasDrafts,
  aliasBusyKey,
  onAliasDraftChange,
  onAddFinancialAlias,
  onRemoveFinancialAlias,
}: FinancialAliasSectionProps) {
  return (
    <article className="summary-card">
      <PanelTitle icon={Fingerprint} kicker={kicker} title={title} />
      <div className="modal-spacing">
        {items.length ? (
          <div className="alias-grid">
            {items.map((item) => {
              const draftKey = `${kind}:${item.entity_id}`;
              const isBusy = aliasBusyKey === draftKey;
              return (
                <article className="data-card data-card-compact alias-card" key={draftKey}>
                  <div className="card-head">
                    <div>
                      <h3>{item.canonical_name}</h3>
                      <p className="meta-line">
                        {kind === "contract"
                          ? item.canonical_client_name || "Contrato sem cliente canônico vinculado"
                          : item.first_period_label && item.last_period_label
                            ? `Presente de ${item.first_period_label} até ${item.last_period_label}`
                            : item.first_period_label || item.last_period_label || "Sem período canônico registrado"}
                      </p>
                      {kind === "contract" ? (
                        <p className="meta-line">
                          {[item.unit, item.contract_start_date, item.contract_end_date].filter(Boolean).join(" | ") ||
                            "Sem unidade ou janela contratual registrada"}
                        </p>
                      ) : null}
                    </div>
                    <StatusPill tone={item.aliases.length ? "ready" : "neutral"} icon={Fingerprint}>
                      {item.aliases.length} alias(es)
                    </StatusPill>
                  </div>

                  {item.aliases.length ? (
                    <div className="alias-chip-grid">
                      {item.aliases.map((alias) => (
                        <button
                          key={`${draftKey}:${alias}`}
                          className="alias-chip-button"
                          type="button"
                          disabled={isBusy}
                          onClick={() => {
                            void onRemoveFinancialAlias(kind, item.entity_id, alias);
                          }}
                        >
                          <span>{alias}</span>
                          <X size={12} />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <EmptyBlock message="Nenhum alias adicional foi registrado ainda para esta entidade." />
                  )}

                  <form
                    className="alias-input-row"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void onAddFinancialAlias(kind, item.entity_id);
                    }}
                  >
                    <TextField
                      label="Novo alias"
                      placeholder={
                        kind === "contract"
                          ? "Ex.: cobrança renova unidade 6"
                          : "Ex.: pix renova ou nome bancário"
                      }
                      value={aliasDrafts[draftKey] || ""}
                      onChange={(event) => onAliasDraftChange(kind, item.entity_id, event.target.value)}
                    />
                    <button className="action-button action-button-ghost alias-add-button" type="submit" disabled={isBusy}>
                      <Plus size={14} />
                      {isBusy ? "Salvando..." : "Salvar"}
                    </button>
                  </form>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyBlock message={emptyMessage} />
        )}
      </div>
    </article>
  );
}

export function WorkspaceUtilityModal({
  activeModal,
  onClose,
  primaryStatusTone,
  status,
  selectedParserProfile,
  reviewData,
  recentAnalysesState,
  isLoadingStoredAnalysis,
  savedAnalysisId,
  setSavedAnalysisId,
  onStoredAnalysisSubmit,
  onStoredAnalysisClick,
  ollamaStatusState,
  recommendedLocalModel,
  onRefreshLocalAi,
  sessionInfo,
  accountProfileForm,
  onAccountProfileFieldChange,
  onAccountProfileSubmit,
  isSavingAccountProfile,
  accountProfileFeedback,
  accountPasswordForm,
  onAccountPasswordFieldChange,
  onAccountPasswordSubmit,
  isSavingAccountPassword,
  accountPasswordFeedback,
  financialAliasesState,
  aliasDrafts,
  aliasBusyKey,
  aliasFeedback,
  onAliasDraftChange,
  onAddFinancialAlias,
  onRemoveFinancialAlias,
  onRefreshFinancialAliases,
}: WorkspaceUtilityModalProps) {
  const isOpen = Boolean(activeModal);
  const titleMap: Record<ActiveUtilityModal, string> = {
    status: "Fluxo e status do workspace",
    analyses: "Análises salvas",
    aliases: "Aliases financeiros",
    "local-ai": "Diagnóstico da IA local",
    account: "Minha conta",
  };
  const subtitleMap: Record<ActiveUtilityModal, string> = {
    status: "Painel resumido de operação, gate de revisão e perfil de parser.",
    analyses: "Abra uma análise recente sem reenviar a planilha.",
    aliases: "Resolva nomes bancários ambíguos e reaproveite esse aprendizado nas próximas conciliações.",
    "local-ai": "Estado do Ollama, latência, modelo recomendado e cargas ativas.",
    account: "Atualize os dados de acesso e mantenha sua sessão pronta para operação.",
  };

  return (
    <ModalFrame
      open={isOpen}
      title={activeModal ? titleMap[activeModal] : "Workspace"}
      subtitle={activeModal ? subtitleMap[activeModal] : ""}
      onClose={onClose}
      size={activeModal === "analyses" || activeModal === "aliases" || activeModal === "account" ? "wide" : "default"}
      actions={
        activeModal === "local-ai" ? (
          <button className="action-button action-button-ghost" type="button" onClick={onRefreshLocalAi}>
            Atualizar diagnostico
          </button>
        ) : activeModal === "aliases" ? (
          <button className="action-button action-button-ghost" type="button" onClick={onRefreshFinancialAliases}>
            Atualizar aliases
          </button>
        ) : null
      }
    >
      {activeModal === "status" ? (
        <div className="modal-stack">
          <article className="summary-card">
            <PanelTitle icon={ShieldCheck} kicker="Operação atual" title="Status principal do workspace" />
            <div className="modal-spacing">
              <StatusBlock tone={primaryStatusTone} message={status.message} />
            </div>
          </article>

          <article className="summary-card">
            <PanelTitle icon={Layers3} kicker="Fluxo recomendado" title="Use a revisão como gate de qualidade" />
            <p className="body-copy modal-spacing">
              O botão final só libera a geração depois que o contexto foi consolidado. Sempre que
              filtros, arquivos ou metadados centrais forem alterados, a revisão volta a ser
              obrigatória para manter o rastro auditável consistente.
            </p>
          </article>

          <article className="summary-card">
            <PanelTitle icon={Filter} kicker="Perfil ativo" title={selectedParserProfile?.label || "Aguardando perfis"} />
            <p className="body-copy modal-spacing">
              {selectedParserProfile?.description ||
                "Os perfis do parser definem o recorte inicial de grupos e status antes da revisão."}
            </p>
            <div className="trace-badges">
              <Tag>Grupos: {selectedParserProfile?.allowed_groups?.join(", ") || "-"}</Tag>
              <Tag>Status: {selectedParserProfile?.allowed_status?.join(", ") || "-"}</Tag>
              {reviewData?.analysis_id ? <Tag icon={FileSearch}>Análise #{reviewData.analysis_id}</Tag> : null}
            </div>
          </article>
        </div>
      ) : null}

      {activeModal === "analyses" ? (
        <div className="modal-stack">
          <form className="saved-analysis-form" onSubmit={onStoredAnalysisSubmit}>
            <input
              type="text"
              inputMode="numeric"
              placeholder="ID da análise"
              value={savedAnalysisId}
              onChange={(event) => setSavedAnalysisId(event.target.value)}
            />
            <button
              className="action-button action-button-ghost saved-analysis-button"
              type="submit"
              disabled={isLoadingStoredAnalysis}
            >
              {isLoadingStoredAnalysis ? "Abrindo..." : "Abrir por ID"}
            </button>
          </form>

          {recentAnalysesState.loading && !recentAnalysesState.items.length ? (
            <EmptyBlock message="Carregando análises recentes..." />
          ) : recentAnalysesState.error && !recentAnalysesState.items.length ? (
            <EmptyBlock message={recentAnalysesState.error} tone="error" />
          ) : recentAnalysesState.items.length ? (
            <div className="saved-analysis-list">
              {recentAnalysesState.items.map((analysis) => {
                const isActive = Number(reviewData?.analysis_id) === Number(analysis.analysis_id);
                return (
                  <button
                    key={analysis.analysis_id}
                    className={`saved-analysis-item ${isActive ? "saved-analysis-item-active" : ""}`}
                    type="button"
                    onClick={() => {
                      void onStoredAnalysisClick(analysis.analysis_id);
                    }}
                    disabled={isLoadingStoredAnalysis}
                  >
                    <div className="saved-analysis-item-head">
                      <strong>Análise #{analysis.analysis_id}</strong>
                      <span>{formatGenerationDate(analysis.created_at) || "Data não registrada"}</span>
                    </div>

                    <p className="saved-analysis-title">
                      {analysis.orgao || analysis.source_filename || "Análise sem entidade identificada"}
                    </p>

                    <p className="meta-line">
                      Perfil {humanizeParserProfile(analysis.parser_profile, analysis.parser_profile || undefined)}
                      {analysis.periodo_analise ? ` | ${analysis.periodo_analise}` : ""}
                    </p>

                    {analysis.checklist_sheet_names?.length ? (
                      <p className="meta-line">Abas: {analysis.checklist_sheet_names.join(", ")}</p>
                    ) : null}

                    <div className="trace-badges saved-analysis-badges">
                      <Tag icon={FileSearch}>{analysis.extracted_item_count} item(ns)</Tag>
                      <Tag icon={Globe2}>{analysis.scraped_page_count} página(s)</Tag>
                      <Tag icon={History}>{analysis.generation_count} execução(ões)</Tag>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <EmptyBlock message="Nenhuma análise salva foi encontrada ainda." />
          )}
        </div>
      ) : null}

      {activeModal === "aliases" ? (
        <div className="modal-stack">
          <article className="summary-card">
            <PanelTitle icon={Fingerprint} kicker="Conciliação assistida" title="Ensine o dicionário canônico do seu financeiro" />
            <p className="body-copy modal-spacing">
              Use aliases para ligar nomes bancários, apelidos ou códigos de cobrança a clientes e contratos
              canônicos. Isso melhora a conciliação futura sem forçar pareamentos arriscados.
            </p>

            {aliasFeedback.message ? (
              <div className="modal-spacing">
                <StatusBlock tone={aliasFeedback.error ? "error" : "ready"} message={aliasFeedback.message} compact />
              </div>
            ) : null}
            {!aliasFeedback.message && financialAliasesState.error ? (
              <div className="modal-spacing">
                <StatusBlock tone="error" message={financialAliasesState.error} compact />
              </div>
            ) : null}

            <div className="trace-badges modal-spacing">
              <Tag icon={Fingerprint}>{financialAliasesState.data?.clients.length || 0} cliente(s) canônicos</Tag>
              <Tag icon={Fingerprint}>{financialAliasesState.data?.contracts.length || 0} contrato(s) canônicos</Tag>
              {financialAliasesState.loading ? <Tag icon={History}>Atualizando lista</Tag> : null}
            </div>
          </article>

          {financialAliasesState.loading && !financialAliasesState.data ? (
            <EmptyBlock message="Carregando aliases financeiros..." />
          ) : financialAliasesState.error && !financialAliasesState.data ? (
            <EmptyBlock message={financialAliasesState.error} tone="error" />
          ) : (
            <>
              <FinancialAliasSection
                title="Clientes canônicos"
                kicker="Escopo de cliente"
                emptyMessage="Nenhum cliente canônico foi encontrado ainda no warehouse financeiro."
                kind="client"
                items={financialAliasesState.data?.clients || []}
                aliasDrafts={aliasDrafts}
                aliasBusyKey={aliasBusyKey}
                onAliasDraftChange={onAliasDraftChange}
                onAddFinancialAlias={onAddFinancialAlias}
                onRemoveFinancialAlias={onRemoveFinancialAlias}
              />
              <FinancialAliasSection
                title="Contratos canônicos"
                kicker="Escopo de contrato"
                emptyMessage="Nenhum contrato canônico foi encontrado ainda no warehouse financeiro."
                kind="contract"
                items={financialAliasesState.data?.contracts || []}
                aliasDrafts={aliasDrafts}
                aliasBusyKey={aliasBusyKey}
                onAliasDraftChange={onAliasDraftChange}
                onAddFinancialAlias={onAddFinancialAlias}
                onRemoveFinancialAlias={onRemoveFinancialAlias}
              />
            </>
          )}
        </div>
      ) : null}

      {activeModal === "local-ai" ? (
        <div className="modal-stack">
          <article className="summary-card">
            <div className="card-head">
              <div>
                <h3>Diagnóstico do Ollama</h3>
                <p className="meta-line">Estado do serviço local antes da geração.</p>
              </div>
              <StatusPill
                tone={
                  ollamaStatusState.loading
                    ? "neutral"
                    : ollamaStatusState.data?.available
                      ? "ready"
                      : "error"
                }
                icon={Bot}
              >
                {ollamaStatusState.loading
                  ? "Consultando"
                  : ollamaStatusState.data?.available
                    ? "Ollama online"
                    : "Ollama indisponível"}
              </StatusPill>
            </div>

            <div className="trace-badges">
              {recommendedLocalModel ? <Tag icon={Sparkles}>Recomendado: {recommendedLocalModel}</Tag> : null}
              {ollamaStatusState.data?.active_model ? <Tag icon={Bot}>Carregado: {ollamaStatusState.data.active_model}</Tag> : null}
              {ollamaStatusState.data?.latency_ms != null ? (
                <Tag icon={Activity}>Ping: {formatDuration(ollamaStatusState.data.latency_ms)}</Tag>
              ) : null}
              {typeof ollamaStatusState.data?.installed_model_count === "number" ? (
                <Tag>Instalados: {ollamaStatusState.data.installed_model_count}</Tag>
              ) : null}
            </div>

            <p className="body-copy modal-spacing">
              {ollamaStatusState.error ||
                ollamaStatusState.data?.message ||
                "Sem diagnóstico do Ollama disponível no momento."}
            </p>
          </article>

          {ollamaStatusState.data?.loaded_models?.length ? (
            <article className="summary-card">
              <PanelTitle icon={Bot} kicker="Cargas ativas" title="Modelos atualmente carregados" />
              <div className="card-grid modal-spacing">
                {ollamaStatusState.data.loaded_models.map((model) => (
                  <article className="data-card" key={model.name}>
                    <h3>{model.name}</h3>
                    <p className="meta-line">
                      VRAM: {model.size_vram ? `${Math.round((model.size_vram / 1024 ** 3) * 10) / 10} GB` : "-"}
                    </p>
                    <p className="meta-line">Contexto: {model.context_length || "-"}</p>
                    <p className="meta-line">Expira em: {model.expires_at || "-"}</p>
                  </article>
                ))}
              </div>
            </article>
          ) : (
            <EmptyBlock message="Nenhum modelo estava carregado no momento da consulta. O Ollama ainda pode estar online e pronto para carregar sob demanda." />
          )}
        </div>
      ) : null}

      {activeModal === "account" ? (
        <div className="modal-stack">
          <article className="summary-card">
            <PanelTitle icon={CheckCircle2} kicker="Sessão atual" title="Rastro operacional ativo" />
            <p className="body-copy modal-spacing">
              Os dados continuam protegidos por conta, e as revisões e gerações agora registram
              também a sessão autenticada que originou cada ação.
            </p>
            <div className="trace-badges">
              {sessionInfo?.session_id ? <Tag icon={CheckCircle2}>Sessão {sessionInfo.session_id}</Tag> : null}
              {sessionInfo?.created_at ? <Tag>Iniciada: {formatGenerationDate(sessionInfo.created_at)}</Tag> : null}
              {sessionInfo?.expires_at ? <Tag>Expira: {formatGenerationDate(sessionInfo.expires_at)}</Tag> : null}
            </div>
          </article>

          <article className="summary-card">
            <PanelTitle icon={UserRoundCog} kicker="Dados da conta" title="Perfil de acesso" />
            <form className="account-form-grid modal-spacing" onSubmit={onAccountProfileSubmit}>
              <div className="field-grid">
                <TextField
                  label="Nome completo"
                  placeholder="Ex.: Ana Rodrigues"
                  value={accountProfileForm.fullName}
                  onChange={(event) => onAccountProfileFieldChange("fullName", event.target.value)}
                />
                <TextField
                  label="E-mail de acesso"
                  type="email"
                  placeholder="voce@empresa.com"
                  value={accountProfileForm.email}
                  onChange={(event) => onAccountProfileFieldChange("email", event.target.value)}
                />
              </div>

              {accountProfileFeedback.message ? (
                <StatusBlock
                  tone={accountProfileFeedback.error ? "error" : "ready"}
                  message={accountProfileFeedback.message}
                  compact
                />
              ) : null}

              <div className="account-form-actions">
                <button className="action-button" type="submit" disabled={isSavingAccountProfile}>
                  {isSavingAccountProfile ? "Salvando..." : "Salvar perfil"}
                </button>
              </div>
            </form>
          </article>

          <article className="summary-card">
            <PanelTitle icon={ShieldCheck} kicker="Segurança" title="Alterar senha" />
            <form className="account-form-grid modal-spacing" onSubmit={onAccountPasswordSubmit}>
              <div className="field-grid">
                <TextField
                  label="Senha atual"
                  type="password"
                  placeholder="Digite a senha atual"
                  value={accountPasswordForm.currentPassword}
                  onChange={(event) => onAccountPasswordFieldChange("currentPassword", event.target.value)}
                />
                <TextField
                  label="Nova senha"
                  type="password"
                  placeholder="Mínimo de 8 caracteres"
                  value={accountPasswordForm.newPassword}
                  onChange={(event) => onAccountPasswordFieldChange("newPassword", event.target.value)}
                />
              </div>

              <TextField
                label="Confirmar nova senha"
                type="password"
                placeholder="Repita a nova senha"
                value={accountPasswordForm.confirmPassword}
                onChange={(event) => onAccountPasswordFieldChange("confirmPassword", event.target.value)}
              />

              {accountPasswordFeedback.message ? (
                <StatusBlock
                  tone={accountPasswordFeedback.error ? "error" : "ready"}
                  message={accountPasswordFeedback.message}
                  compact
                />
              ) : null}

              <div className="account-form-actions">
                <button className="action-button" type="submit" disabled={isSavingAccountPassword}>
                  {isSavingAccountPassword ? "Atualizando..." : "Atualizar senha"}
                </button>
              </div>
            </form>
          </article>
        </div>
      ) : null}
    </ModalFrame>
  );
}
