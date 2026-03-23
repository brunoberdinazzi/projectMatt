import { motion } from "framer-motion";
import {
  Activity,
  FileSearch,
  Filter,
  Globe2,
  History,
  ShieldCheck,
} from "lucide-react";

import {
  formatGenerationDate,
  humanizeParserProfile,
} from "../lib/app-utils";
import {
  EmptyBlock,
  PanelTitle,
  StatusBlock,
  Tag,
} from "./ui";

const PANEL_VARIANTS = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
};

export function WorkspaceSidebar({
  primaryStatusTone,
  status,
  recentAnalysesState,
  reviewData,
  isLoadingStoredAnalysis,
  handleStoredAnalysisSubmit,
  savedAnalysisId,
  setSavedAnalysisId,
  handleLoadStoredAnalysis,
  selectedParserProfile,
}) {
  return (
    <aside className="workspace-sidebar">
      <motion.section className="sidebar-card" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
        <PanelTitle icon={ShieldCheck} kicker="Fluxo recomendado" title="Use a revisao como gate de qualidade." />
        <p className="sidebar-copy">
          O botao final so libera a geracao depois que o contexto foi consolidado. Sempre que
          voce alterar filtros, arquivos ou metadados centrais, a revisao volta a ficar
          obrigatoria.
        </p>
      </motion.section>

      <motion.section className="sidebar-card sidebar-card-status" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
        <PanelTitle icon={Activity} kicker="Operacao atual" title="Status principal do workspace" />
        <StatusBlock tone={primaryStatusTone} message={status.message} />
      </motion.section>

      <motion.section className="sidebar-card" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
        <PanelTitle icon={History} kicker="Analises salvas" title="Retome uma revisao existente" />
        <p className="sidebar-copy">
          Abra uma analise recente sem reenviar a planilha. Se precisarmos mudar a extracao,
          basta importar o arquivo novamente e rodar a revisao de novo.
        </p>

        <form className="saved-analysis-form" onSubmit={handleStoredAnalysisSubmit}>
          <input
            type="text"
            inputMode="numeric"
            placeholder="ID da analise"
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
          <EmptyBlock message="Carregando analises recentes..." />
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
                  onClick={() => void handleLoadStoredAnalysis(analysis.analysis_id)}
                  disabled={isLoadingStoredAnalysis}
                >
                  <div className="saved-analysis-item-head">
                    <strong>Analise #{analysis.analysis_id}</strong>
                    <span>{formatGenerationDate(analysis.created_at) || "Data nao registrada"}</span>
                  </div>

                  <p className="saved-analysis-title">
                    {analysis.orgao || analysis.source_filename || "Analise sem entidade identificada"}
                  </p>

                  <p className="meta-line">
                    Perfil {humanizeParserProfile(analysis.parser_profile, analysis.parser_profile)}
                    {analysis.periodo_analise ? ` | ${analysis.periodo_analise}` : ""}
                  </p>

                  {Array.isArray(analysis.checklist_sheet_names) && analysis.checklist_sheet_names.length ? (
                    <p className="meta-line">
                      Abas: {analysis.checklist_sheet_names.join(", ")}
                    </p>
                  ) : null}

                  <div className="trace-badges saved-analysis-badges">
                    <Tag icon={FileSearch}>{analysis.extracted_item_count} item(ns)</Tag>
                    <Tag icon={Globe2}>{analysis.scraped_page_count} pagina(s)</Tag>
                    <Tag icon={History}>{analysis.generation_count} execucao(oes)</Tag>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <EmptyBlock message="Nenhuma analise salva foi encontrada ainda." />
        )}
      </motion.section>

      <motion.section className="sidebar-card" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
        <PanelTitle icon={Filter} kicker="Perfil ativo" title={selectedParserProfile?.label || "Aguardando perfis"} />
        <p className="sidebar-copy">
          {selectedParserProfile?.description ||
            "Os perfis do parser definem o recorte inicial de grupos e status antes da revisao."}
        </p>
        <div className="sidebar-tags">
          <Tag>Grupos: {selectedParserProfile?.allowed_groups?.join(", ") || "-"}</Tag>
          <Tag>Status: {selectedParserProfile?.allowed_status?.join(", ") || "-"}</Tag>
        </div>
      </motion.section>
    </aside>
  );
}
