import { AnimatePresence, motion } from "framer-motion";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Bot, BrainCircuit, CheckCircle2, ShieldCheck, UploadCloud, X } from "lucide-react";

import {
  formatDuration,
  formatGenerationDate,
  humanizeGenerationMode,
  humanizeProvider,
} from "../lib/app-utils";
import type {
  GenerationTraceItem,
  ModalFrameSize,
  SelectOption,
  StatusTone,
  TabDescriptor,
  WorkspaceMetric,
} from "../types/workspace";

const MODAL_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

interface PanelTitleProps {
  icon: LucideIcon;
  kicker: string;
  title: string;
}

export function PanelTitle({ icon: Icon, kicker, title }: PanelTitleProps) {
  return (
    <div className="sidebar-head">
      <span className="icon-badge">
        <Icon size={16} />
      </span>
      <div>
        <span className="eyebrow eyebrow-soft">{kicker}</span>
        <h3>{title}</h3>
      </div>
    </div>
  );
}

interface StatusBlockProps {
  tone: StatusTone | string;
  message: string;
  compact?: boolean;
}

export function StatusBlock({ tone, message, compact = false }: StatusBlockProps) {
  return <p className={`status-block status-${tone} ${compact ? "status-compact" : ""}`}>{message}</p>;
}

interface StatusPillProps {
  tone: StatusTone | string;
  icon?: LucideIcon;
  children?: ReactNode;
}

export function StatusPill({ tone, icon: Icon, children }: StatusPillProps) {
  return (
    <span className={`status-pill status-pill-${tone}`}>
      {Icon ? <Icon size={14} /> : null}
      {children}
    </span>
  );
}

interface IconCopyProps {
  icon: LucideIcon;
  label?: string;
  title?: string;
  copy: string;
}

export function InsightChip({ icon: Icon, label, copy }: IconCopyProps) {
  return (
    <div className="insight-chip">
      <span className="icon-badge icon-badge-soft">
        <Icon size={16} />
      </span>
      <div>
        <strong>{label}</strong>
        <span>{copy}</span>
      </div>
    </div>
  );
}

export function TimelineStep({ icon: Icon, title, copy }: IconCopyProps) {
  return (
    <div className="timeline-step">
      <span className="icon-badge icon-badge-soft">
        <Icon size={16} />
      </span>
      <div>
        <h3>{title}</h3>
        <p>{copy}</p>
      </div>
    </div>
  );
}

export function MetricCard({ icon: Icon, label, value }: WorkspaceMetric) {
  return (
    <div className="metric-card">
      <div className="metric-label">
        <span className="icon-badge icon-badge-soft">
          <Icon size={16} />
        </span>
        <span>{label}</span>
      </div>
      <strong className="metric-value" title={value || "-"}>
        {value || "-"}
      </strong>
    </div>
  );
}

interface GuideCardProps {
  icon: LucideIcon;
  title: string;
  copy: string;
}

export function GuideCard({ icon: Icon, title, copy }: GuideCardProps) {
  return (
    <article className="guide-card">
      <span className="icon-badge icon-badge-soft">
        <Icon size={16} />
      </span>
      <h3>{title}</h3>
      <p>{copy}</p>
    </article>
  );
}

interface TabStripProps {
  tabs: TabDescriptor[];
  activeKey: string;
  onChange: (key: string) => void;
}

export function TabStrip({ tabs, activeKey, onChange }: TabStripProps) {
  return (
    <div className="tab-strip" role="tablist" aria-label="Navegacao de contexto">
      {tabs.map(({ key, label, icon: Icon, count }) => {
        const isActive = key === activeKey;
        return (
          <button
            key={key}
            className={`tab-button ${isActive ? "tab-button-active" : ""}`}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(key)}
          >
            <span className="tab-button-label">
              <Icon size={15} />
              {label}
            </span>
            {typeof count === "number" ? <span className="tab-count">{count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

interface SectionCardProps {
  number: string;
  icon: LucideIcon;
  title: string;
  copy: string;
  children?: ReactNode;
}

export function SectionCard({ number, icon: Icon, title, copy, children }: SectionCardProps) {
  return (
    <section className="section-card">
      <div className="section-head">
        <div className="section-title">
          <span className="section-number">{number}</span>
          <div>
            <h3>{title}</h3>
            <p>{copy}</p>
          </div>
        </div>
        <span className="icon-badge">
          <Icon size={18} />
        </span>
      </div>
      {children}
    </section>
  );
}

interface FieldFrameProps {
  label: string;
  helper?: string;
  children?: ReactNode;
}

function FieldFrame({ label, helper, children }: FieldFrameProps) {
  return (
    <label className="field-frame">
      <span className="field-label">{label}</span>
      {children}
      {helper ? <small className="field-helper">{helper}</small> : null}
    </label>
  );
}

type TextFieldProps = {
  label: string;
  helper?: string;
} & ComponentPropsWithoutRef<"input">;

export function TextField({ label, helper, ...props }: TextFieldProps) {
  return (
    <FieldFrame label={label} helper={helper}>
      <input {...props} />
    </FieldFrame>
  );
}

type SelectFieldProps<T extends string = string> = {
  label: string;
  helper?: string;
  options: ReadonlyArray<SelectOption<T>>;
} & ComponentPropsWithoutRef<"select">;

export function SelectField<T extends string = string>({
  label,
  helper,
  options,
  ...props
}: SelectFieldProps<T>) {
  return (
    <FieldFrame label={label} helper={helper}>
      <select {...props}>
        {options.map((option) => (
          <option key={`${label}-${String(option.value)}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldFrame>
  );
}

type TextAreaFieldProps = {
  label: string;
  helper?: string;
} & ComponentPropsWithoutRef<"textarea">;

export function TextAreaField({ label, helper, ...props }: TextAreaFieldProps) {
  return (
    <FieldFrame label={label} helper={helper}>
      <textarea {...props} />
    </FieldFrame>
  );
}

type FileFieldProps = {
  label: string;
  helper?: string;
} & Omit<ComponentPropsWithoutRef<"input">, "type">;

export function FileField({ label, helper, ...props }: FileFieldProps) {
  return (
    <FieldFrame label={label} helper={helper}>
      <div className="file-shell">
        <UploadCloud size={18} />
        <input {...props} type="file" />
      </div>
    </FieldFrame>
  );
}

interface ReviewSectionProps {
  title: string;
  subtitle: string;
  children?: ReactNode;
}

export function ReviewSection({ title, subtitle, children }: ReviewSectionProps) {
  return (
    <section className="review-section">
      <div className="review-section-head">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

interface EmptyBlockProps {
  message: string;
  tone?: StatusTone | string;
}

export function EmptyBlock({ message, tone = "neutral" }: EmptyBlockProps) {
  return <div className={`empty-block empty-${tone}`}>{message}</div>;
}

interface PreBlockProps {
  text: string;
}

export function PreBlock({ text }: PreBlockProps) {
  return <pre className="pre-block">{text}</pre>;
}

interface TagProps {
  icon?: LucideIcon;
  children?: ReactNode;
}

export function Tag({ icon: Icon, children }: TagProps) {
  return (
    <span className="tag" title={typeof children === "string" ? children : undefined}>
      {Icon ? <Icon size={12} /> : null}
      {children}
    </span>
  );
}

interface TraceCardProps {
  trace: GenerationTraceItem;
  isHighlighted: boolean;
}

export function TraceCard({ trace, isHighlighted }: TraceCardProps) {
  const promptLength = trace.prompt_snapshot?.trim().length ?? 0;
  const rawResponseLength = trace.raw_response?.trim().length ?? 0;
  return (
    <article className={`trace-card generation-trace-card ${isHighlighted ? "trace-card-highlighted" : ""}`}>
      <div className="card-head">
        <div>
          <h3>Execução #{trace.id || "-"}</h3>
          <p className="meta-line">{formatGenerationDate(trace.created_at) || "Data não registrada"}</p>
        </div>
        <StatusPill tone={isHighlighted ? "ready" : "neutral"} icon={CheckCircle2}>
          {isHighlighted ? "Última execução" : "Execução registrada"}
        </StatusPill>
      </div>

      <div className="trace-badges">
        <Tag icon={Bot}>{humanizeProvider(trace.provider)}</Tag>
        {trace.model_name ? <Tag icon={BrainCircuit}>{trace.model_name}</Tag> : null}
        {trace.session_public_id ? <Tag icon={ShieldCheck}>Sessão {trace.session_public_id}</Tag> : null}
        {trace.fallback_reason ? <Tag icon={AlertTriangle}>Fallback registrado</Tag> : null}
      </div>

      <div className="generation-summary-grid">
        <div className="generation-summary-item">
          <span>Modo solicitado</span>
          <strong>{humanizeGenerationMode(trace.requested_mode)}</strong>
        </div>
        <div className="generation-summary-item">
          <span>Modo executado</span>
          <strong>{humanizeGenerationMode(trace.used_mode)}</strong>
        </div>
        <div className="generation-summary-item">
          <span>Saída</span>
          <strong>{(trace.output_format || "docx").toUpperCase()}</strong>
        </div>
        <div className="generation-summary-item">
          <span>Tempo</span>
          <strong>{trace.duration_ms != null ? formatDuration(trace.duration_ms) : "-"}</strong>
        </div>
      </div>

      {trace.fallback_reason ? (
        <div className="generation-callout generation-callout-warning">
          <strong>Fallback aplicado</strong>
          <p>{trace.fallback_reason}</p>
        </div>
      ) : null}

      {trace.prompt_snapshot ? (
        <details className="trace-details">
          <summary>Prompt salvo {promptLength ? `(${promptLength} caracteres)` : ""}</summary>
          <PreBlock text={trace.prompt_snapshot} />
        </details>
      ) : null}

      {trace.raw_response ? (
        <details className="trace-details">
          <summary>Resposta bruta {rawResponseLength ? `(${rawResponseLength} caracteres)` : ""}</summary>
          <PreBlock text={trace.raw_response} />
        </details>
      ) : null}
    </article>
  );
}

interface ModalFrameProps {
  open: boolean;
  title: string;
  subtitle?: string | null;
  onClose: () => void;
  children?: ReactNode;
  actions?: ReactNode;
  size?: ModalFrameSize;
}

export function ModalFrame({
  open,
  title,
  subtitle,
  onClose,
  children,
  actions = null,
  size = "default",
}: ModalFrameProps) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          role="presentation"
          onClick={onClose}
        >
          <motion.div
            className={`modal-shell modal-shell-${size}`}
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 18, scale: 0.98 }}
            transition={{ duration: 0.2, ease: MODAL_EASE }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-head">
              <div>
                <h3>{title}</h3>
                {subtitle ? <p>{subtitle}</p> : null}
              </div>
              <button className="modal-close" type="button" onClick={onClose} aria-label="Fechar modal">
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">{children}</div>
            {actions ? <div className="modal-actions">{actions}</div> : null}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
