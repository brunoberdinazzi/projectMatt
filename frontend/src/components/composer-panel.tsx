import { motion } from "framer-motion";
import type { ChangeEventHandler, FormEventHandler } from "react";
import { Filter, FileText, History, Sparkles, UploadCloud } from "lucide-react";

import {
  buildParserProfileHint,
  describeSelectedFile,
  describeSelectedFiles,
  GENERATION_MODE_HINTS,
  GENERATION_MODE_OPTIONS,
  LAYOUT_OPTIONS,
  OUTPUT_FORMAT_OPTIONS,
} from "../lib/app-utils";
import type {
  AppFormState,
  ParserDetectionState,
  ParserProfileDefinition,
  SelectOption,
  StatusFeedback,
  StatusTone,
} from "../types/workspace";
import {
  FileField,
  GuideCard,
  SectionCard,
  SelectField,
  StatusBlock,
  TextAreaField,
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

interface ComposerPanelProps {
  formState: AppFormState;
  selectedParserProfile: ParserProfileDefinition | null;
  activeParserProfile: ParserProfileDefinition | null;
  parserProfiles: ParserProfileDefinition[];
  parserDetectionState: ParserDetectionState;
  ollamaModels: string[];
  recommendedLocalModel: string;
  applyFormValue: (
    name: keyof AppFormState,
    value: AppFormState[keyof AppFormState],
    options?: { markStale?: boolean }
  ) => void;
  handleFileChange: ChangeEventHandler<HTMLInputElement>;
  handleTemplateChange: ChangeEventHandler<HTMLInputElement>;
  handleReviewRequest: FormEventHandler<HTMLFormElement>;
  primaryStatusTone: StatusTone;
  status: StatusFeedback;
  isLoadingReview: boolean;
  reviewReady: boolean;
  isGenerating: boolean;
  handleGenerateReport: () => void | Promise<void>;
}

function buildLocalModelOptions(ollamaModels: string[], recommendedLocalModel: string): SelectOption[] {
  return [
    {
      value: "",
      label: recommendedLocalModel
        ? `Seleção automática (prioriza ${recommendedLocalModel})`
        : "Seleção automática",
    },
    ...ollamaModels.map((model) => ({
      value: model,
      label: model === recommendedLocalModel ? `${model} (Recomendado)` : model,
    })),
  ];
}

function buildParserProfileOptions(parserProfiles: ParserProfileDefinition[]): SelectOption[] {
  if (parserProfiles.length) {
    return parserProfiles.map((profile) => ({ value: profile.key, label: profile.label }));
  }
  return [
    { value: "auto", label: "Automático" },
    { value: "default", label: "Padrão" },
    { value: "extended", label: "Estendido" },
    { value: "full", label: "Completo" },
    { value: "financial_dre", label: "Financeiro / DRE" },
  ];
}

export function ComposerPanel({
  formState,
  selectedParserProfile,
  activeParserProfile,
  parserProfiles,
  parserDetectionState,
  ollamaModels,
  recommendedLocalModel,
  applyFormValue,
  handleFileChange,
  handleTemplateChange,
  handleReviewRequest,
  primaryStatusTone,
  status,
  isLoadingReview,
  reviewReady,
  isGenerating,
  handleGenerateReport,
}: ComposerPanelProps) {
  const isFinancialProfile =
    activeParserProfile?.key === "financial_dre" ||
    parserDetectionState.data?.resolved_profile === "financial_dre" ||
    formState.parserProfile === "financial_dre";
  const parserDetectionTone: StatusTone = parserDetectionState.error
    ? "error"
    : parserDetectionState.data
      ? "ready"
      : "idle";
  const parserDetectionMessage = !formState.files.length
    ? "Selecione um arquivo para identificar automaticamente o parser antes da revisão completa."
    : formState.parserProfile !== "auto"
      ? `Perfil manual ativo: ${selectedParserProfile?.label || "Personalizado"}. A detecção automática fica pausada até você voltar para Automático.`
      : parserDetectionState.loading
        ? formState.files.length > 1
          ? "Inspecionando o primeiro arquivo da seleção para definir o parser recomendado do lote."
          : "Inspecionando a estrutura do arquivo para definir o parser recomendado."
        : parserDetectionState.error
          ? parserDetectionState.error
          : parserDetectionState.data
            ? `Detectado: ${parserDetectionState.data.resolved_label}. ${parserDetectionState.data.message || "Esse perfil será confirmado na revisão completa."}${formState.files.length > 1 ? " O lote só será consolidado se todos os arquivos forem financeiros." : ""}`
            : "A detecção será executada assim que o arquivo estiver disponível.";

  return (
    <motion.section className="glass-panel composer-panel" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
      <div className="panel-header">
        <div>
          <span className="eyebrow">Workspace</span>
          <h2>
            {isFinancialProfile
              ? "Prepare a leitura financeira antes de exportar"
              : "Prepare a análise antes de gerar"}
          </h2>
        </div>
        <p className="panel-copy">
          {isFinancialProfile
            ? "Organize leitura, consolidação mensal e composição do demonstrativo."
            : "Organize leitura, revisão e composição do documento final."}
        </p>
      </div>

      <div className="workflow-grid">
        <GuideCard
          icon={UploadCloud}
          title="Arquivos"
          copy="Arquivos alimentam a leitura; o template preserva a apresentação."
        />
        <GuideCard
          icon={Filter}
          title={isFinancialProfile ? "Escopo financeiro" : "Recorte"}
          copy={
            isFinancialProfile
              ? "Defina quais abas e meses entram na DRE consolidada."
              : "Perfil, grupos e status definem o que vira item elegível."
          }
        />
        <GuideCard
          icon={Sparkles}
          title="Composição"
          copy="O modo decide entre IA remota, Ollama local ou regras."
        />
        <GuideCard
          icon={History}
          title="Auditoria"
          copy="Execuções relevantes ficam registradas com provedor, modelo e duração."
        />
      </div>

      <form className="composer-form" onSubmit={handleReviewRequest}>
        <SectionCard
          number="01"
          icon={UploadCloud}
          title="Arquivos e saída"
          copy="Defina os arquivos e o modo de composição."
        >
          <div className="field-grid field-grid-wide">
            <FileField
              label={isFinancialProfile || formState.parserProfile === "auto" ? "Planilha ou extrato financeiro" : "Planilha Excel"}
              accept={isFinancialProfile || formState.parserProfile === "auto" ? ".xlsx,.xlsm,.pdf" : ".xlsx,.xlsm"}
              multiple={formState.parserProfile === "auto" || isFinancialProfile}
              helper={describeSelectedFiles(
                formState.files,
                isFinancialProfile || formState.parserProfile === "auto"
                  ? "Selecione uma ou mais planilhas ou extratos PDF. A consolidação multi-arquivo fica disponível para DRE."
                  : "Nenhuma planilha selecionada."
              )}
              onChange={handleFileChange}
              required
            />
            <FileField
              label="Template DOCX do relatório"
              accept=".docx"
              helper={describeSelectedFile(
                formState.templateFile,
                "Opcional. Preserva cabeçalho, rodapé, logotipo e estilos."
              )}
              onChange={handleTemplateChange}
            />
          </div>

          <div className="field-grid">
            <SelectField
              label="Formato de saída"
              value={formState.outputFormat}
              onChange={(event) => applyFormValue("outputFormat", event.target.value)}
              options={OUTPUT_FORMAT_OPTIONS}
            />
            <SelectField
              label="Modo de geração"
              value={formState.generationMode}
              onChange={(event) => applyFormValue("generationMode", event.target.value)}
              options={GENERATION_MODE_OPTIONS}
              helper={GENERATION_MODE_HINTS[formState.generationMode]}
            />
          </div>

          <div className="field-grid">
            <SelectField
              label="Modelo local do Ollama"
              value={formState.localModel}
              disabled={!["auto", "local"].includes(formState.generationMode)}
              onChange={(event) => applyFormValue("localModel", event.target.value)}
              helper={
                ollamaModels.length
                  ? `Modelos detectados: ${ollamaModels.join(", ")}${
                      recommendedLocalModel ? ` | Recomendado para o fluxo local: ${recommendedLocalModel}` : ""
                    }${
                      recommendedLocalModel.startsWith("deepseek-r1")
                        ? " | Esse modelo tende a entregar melhor qualidade local, mas pode levar mais tempo para gerar."
                        : ""
                    }`
                  : "Nenhum modelo local detectado no momento."
              }
              options={buildLocalModelOptions(ollamaModels, recommendedLocalModel)}
            />
          </div>
        </SectionCard>

        <SectionCard
          number="02"
          icon={Filter}
          title={isFinancialProfile ? "Escopo financeiro" : "Escopo do parser"}
          copy={
            isFinancialProfile
              ? "Defina como abas e meses entram no demonstrativo."
              : "Controle o que entra na revisão antes da composição."
          }
        >
          <div className="field-grid">
            <SelectField
              label="Perfil do parser"
              value={formState.parserProfile}
              onChange={(event) => applyFormValue("parserProfile", event.target.value)}
              helper={buildParserProfileHint(selectedParserProfile)}
              options={buildParserProfileOptions(parserProfiles)}
            />
            {!isFinancialProfile ? (
              <TextField
                label="Grupos permitidos"
                placeholder="Ex.: 1,5 ou 1,2,3,4,5"
                value={formState.allowedGroups}
                onChange={(event) => applyFormValue("allowedGroups", event.target.value)}
              />
            ) : null}
          </div>

          <StatusBlock tone={parserDetectionTone} message={parserDetectionMessage} />

          <div className={`field-grid ${isFinancialProfile ? "field-grid-single" : ""}`}>
            {!isFinancialProfile ? (
              <TextField
                label="Status permitidos"
                placeholder="Ex.: Nao, Parcialmente"
                value={formState.allowedStatus}
                onChange={(event) => applyFormValue("allowedStatus", event.target.value)}
              />
            ) : null}
            <TextField
              label={isFinancialProfile ? "Abas financeiras" : "Abas do checklist"}
              helper={
                formState.parserProfile === "auto"
                  ? "Opcional. Deixe em branco para a detecção automática escolher o parser e as abas compatíveis do workbook."
                  : isFinancialProfile
                    ? "Opcional. Deixe em branco para detectar automaticamente os meses ou informe várias abas separadas por vírgula."
                    : "Opcional. Deixe em branco para detectar automaticamente ou informe várias abas separadas por vírgula."
              }
              placeholder={
                isFinancialProfile
                  ? "Ex.: Janeiro, Fevereiro, Marco"
                  : "Ex.: Checklist, Checklist Complementar"
              }
              value={formState.checklistSheetName}
              onChange={(event) => applyFormValue("checklistSheetName", event.target.value)}
            />
          </div>
        </SectionCard>

        <SectionCard
          number="03"
          icon={FileText}
          title="Metadados do documento"
          copy={
            isFinancialProfile
              ? "Esses campos identificam empresa, período e apresentação final."
              : "Esses campos alimentam capa, contexto e fechamento."
          }
        >
          <div className="field-grid">
            <TextField
              label="Período da análise"
              placeholder="Ex.: Ciclo Q4/2025"
              value={formState.periodoAnalise}
              onChange={(event) => applyFormValue("periodoAnalise", event.target.value)}
            />
            <TextField
              label="Número do documento"
              placeholder="Ex.: REP-022/2025"
              value={formState.numeroRelatorio}
              onChange={(event) => applyFormValue("numeroRelatorio", event.target.value)}
            />
          </div>

          <div className="field-grid">
            <TextField
              label="Ticket ou solicitação"
              placeholder="Ex.: TASK-5492"
              value={formState.solicitacao}
              onChange={(event) => applyFormValue("solicitacao", event.target.value)}
            />
            <TextField
              label="Área solicitante"
              placeholder="Ex.: Operações, Auditoria ou PMO"
              value={formState.requesterArea}
              onChange={(event) => applyFormValue("requesterArea", event.target.value)}
            />
          </div>

          <div className="field-grid">
            <TextField
              label="Referência"
              placeholder="Ex.: PROC-09.2024.00009414-6"
              value={formState.referencia}
              onChange={(event) => applyFormValue("referencia", event.target.value)}
            />
            <TextField
              label="Documento de referência"
              placeholder="Ex.: DOC-145/2025"
              value={formState.relatorioContabilReferencia}
              onChange={(event) => applyFormValue("relatorioContabilReferencia", event.target.value)}
            />
          </div>

          <div className="field-grid">
            <TextField
              label="Local de emissão"
              placeholder="Ex.: Sao Paulo/SP"
              value={formState.cidadeEmissao}
              onChange={(event) => applyFormValue("cidadeEmissao", event.target.value)}
            />
            <TextField
              label="Data de emissão"
              placeholder="Ex.: 18 de dezembro de 2025"
              value={formState.dataEmissao}
              onChange={(event) => applyFormValue("dataEmissao", event.target.value)}
            />
          </div>

          <div className="field-grid">
            <TextField
              label="Período de coleta"
              placeholder="Ex.: entre 12 e 16 de dezembro de 2025"
              value={formState.periodoColeta}
              onChange={(event) => applyFormValue("periodoColeta", event.target.value)}
            />
            <TextField
              label="Entidade"
              placeholder="Ex.: Cliente, unidade ou organização analisada"
              value={formState.orgao}
              onChange={(event) => applyFormValue("orgao", event.target.value)}
            />
          </div>

          {!isFinancialProfile ? (
            <div className="field-grid">
              <SelectField
                label="Perfil de layout"
                value={formState.layoutProfile}
                onChange={(event) => applyFormValue("layoutProfile", event.target.value)}
                options={LAYOUT_OPTIONS}
              />
            </div>
          ) : null}

          <TextAreaField
            label="Equipe técnica"
            placeholder="Ex.: Nome do responsavel - Cargo - Especialidade"
            value={formState.equipeTecnica}
            onChange={(event) => applyFormValue("equipeTecnica", event.target.value)}
          />
        </SectionCard>

        <div className="action-bar">
          <div className="action-copy">
            <span className="eyebrow eyebrow-soft">Status do fluxo</span>
            <StatusBlock tone={primaryStatusTone} message={status.message} compact />
          </div>
          <div className="action-buttons">
            <button className="action-button action-button-ghost" type="submit" disabled={isLoadingReview}>
              {isLoadingReview ? "Analisando..." : "Analisar contexto e evidências"}
            </button>
            <button
              className="action-button"
              type="button"
              disabled={!reviewReady || isGenerating}
              onClick={() => {
                void handleGenerateReport();
              }}
            >
              {isGenerating ? "Gerando..." : "Gerar relatório final"}
            </button>
          </div>
        </div>
      </form>
    </motion.section>
  );
}
