import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BrainCircuit,
  FileSpreadsheet,
  Filter,
  Radar,
  ScanSearch,
  UploadCloud,
  Wand2,
} from "lucide-react";

import {
  InsightChip,
  MetricCard,
  StatusPill,
  TimelineStep,
} from "./ui";
import type { StatusTone, WorkspaceMetric } from "../types/workspace";

const PANEL_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

const PANEL_VARIANTS = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: PANEL_EASE },
  },
};

const STAGGER_VARIANTS = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.06,
      delayChildren: 0.04,
    },
  },
};

interface WorkspaceHeroProps {
  primaryStatusTone: StatusTone;
  reviewReady: boolean;
  studioMetrics: WorkspaceMetric[];
}

function resolveHeroStatusIcon(tone: StatusTone): LucideIcon {
  return tone === "error" ? AlertTriangle : Activity;
}

export function WorkspaceHero({ primaryStatusTone, reviewReady, studioMetrics }: WorkspaceHeroProps) {
  return (
    <motion.header className="hero-shell" initial="hidden" animate="visible" variants={STAGGER_VARIANTS}>
      <motion.section className="hero-panel hero-panel-main" variants={PANEL_VARIANTS}>
        <div className="hero-kicker-row">
          <span className="eyebrow">Draux Inc.</span>
          <StatusPill tone={primaryStatusTone} icon={resolveHeroStatusIcon(primaryStatusTone)}>
            {primaryStatusTone === "error"
              ? "Revisão pendente"
              : reviewReady
                ? "Pronto para gerar"
                : "Workspace preparado"}
          </StatusPill>
        </div>

        <h1>Revisão, web e geração no mesmo workspace.</h1>
        <p className="hero-lead">
          Configuração, revisão e geração em etapas claras, com menos ruído na operação diária.
        </p>

        <div className="hero-actions">
          <a className="primary-link" href="#workspace">
            Abrir fluxo
            <ArrowRight size={18} />
          </a>
          <a className="secondary-link" href="#crawler">
            Crawler
            <ArrowUpRight size={18} />
          </a>
        </div>

        <div className="hero-chip-grid">
          <InsightChip icon={UploadCloud} label="Entrada auditável" copy="Arquivos, template e metadados." />
          <InsightChip icon={ScanSearch} label="Revisão guiada" copy="Itens, alertas e evidências." />
          <InsightChip icon={BrainCircuit} label="Geração rastreável" copy="Modelo, fallback e tempo." />
        </div>
      </motion.section>

      <motion.aside className="hero-panel hero-panel-aside" variants={PANEL_VARIANTS}>
        <div className="dashboard-head">
          <p className="eyebrow eyebrow-soft">Resumo ao vivo</p>
          <h2>Resumo da operação</h2>
        </div>

        <div className="dashboard-grid">
          {studioMetrics.map((metric) => (
            <MetricCard key={metric.label} icon={metric.icon} label={metric.label} value={metric.value} />
          ))}
        </div>

        <div className="timeline-card">
          <TimelineStep
            icon={FileSpreadsheet}
            title="1. Configure a entrada"
            copy="Arquivos, template e estratégia."
          />
          <TimelineStep
            icon={Filter}
            title="2. Recorte o parser"
            copy="Grupos, status e abas."
          />
          <TimelineStep
            icon={Radar}
            title="3. Audite o contexto"
            copy="Alertas, itens e prompt."
          />
          <TimelineStep
            icon={Wand2}
            title="4. Gere o documento"
            copy="Exporte com rastreabilidade."
          />
        </div>
      </motion.aside>
    </motion.header>
  );
}
