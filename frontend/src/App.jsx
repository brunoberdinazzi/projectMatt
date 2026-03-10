import {
  startTransition,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Clock3,
  FileSearch,
  FileSpreadsheet,
  FileText,
  Filter,
  Globe2,
  History,
  Link2,
  Radar,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  TimerReset,
  UploadCloud,
  Wand2,
  Waypoints,
} from "lucide-react";

const INITIAL_FORM_STATE = {
  file: null,
  templateFile: null,
  outputFormat: "docx",
  generationMode: "auto",
  localModel: "",
  parserProfile: "extended",
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

const GENERATION_MODE_HINTS = {
  auto: "Equilibra qualidade e resiliencia com fallback entre provedores e regras locais.",
  local: "Forca a redacao no Ollama local e respeita o modelo selecionado.",
  ai: "Usa o provedor remoto configurado no backend para compor o texto.",
  rules: "Ignora IA e gera o conteudo com regras locais deterministicas.",
};

const GENERATION_MODE_OPTIONS = [
  { value: "auto", label: "Automatico" },
  { value: "local", label: "Local (Ollama)" },
  { value: "ai", label: "IA remota" },
  { value: "rules", label: "Regras" },
];

const OUTPUT_FORMAT_OPTIONS = [
  { value: "docx", label: "DOCX" },
  { value: "pdf", label: "PDF" },
];

const LAYOUT_OPTIONS = [
  { value: "", label: "Detectar automaticamente" },
  { value: "profile_a", label: "Perfil A" },
  { value: "profile_b", label: "Perfil B" },
];

const SOURCE_LABELS = {
  site_orgao: "Canal principal",
  portal_transparencia: "Canal complementar",
  esic: "Canal de atendimento",
  nao_informada: "Fonte nao identificada",
};

const CATEGORY_LABELS = {
  esic: "Canal de atendimento",
  portal_transparencia: "Portal complementar",
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

const DESTINATION_LABELS = {
  pagina: "Pagina",
  pdf: "PDF",
  csv: "CSV",
  planilha: "Planilha",
  documento: "Documento",
  arquivo: "Arquivo",
};

const GENERATION_MODE_LABELS = {
  auto: "Automatico",
  local: "Ollama local",
  ai: "IA remota",
  rules: "Regras",
};

const PROVIDER_LABELS = {
  ollama: "Ollama",
  openai: "OpenAI",
  rules: "Regras locais",
};

const PANEL_VARIANTS = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
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

export default function App() {
  const [formState, setFormState] = useState(INITIAL_FORM_STATE);
  const [status, setStatus] = useState({
    message: "Preencha os campos e execute a revisao para liberar a geracao final.",
    error: false,
  });
  const [scrapeStatus, setScrapeStatus] = useState({
    message: "Informe uma URL e execute o crawler para inspecionar a origem manualmente.",
    error: false,
  });
  const [reviewData, setReviewData] = useState(null);
  const [reviewStale, setReviewStale] = useState(false);
  const [generationHistoryState, setGenerationHistoryState] = useState({
    loading: false,
    error: "",
    items: [],
  });
  const [highlightGenerationId, setHighlightGenerationId] = useState(null);
  const [scrapeResult, setScrapeResult] = useState(null);
  const [ollamaModels, setOllamaModels] = useState([]);
  const [parserProfiles, setParserProfiles] = useState([]);
  const [isLoadingReview, setIsLoadingReview] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isScraping, setIsScraping] = useState(false);
  const [activeReviewTab, setActiveReviewTab] = useState("overview");
  const [activeScrapeTab, setActiveScrapeTab] = useState("links");

  const deferredReview = useDeferredValue(reviewData);
  const reviewPanelRef = useRef(null);
  const scrapeResultRef = useRef(null);
  const generationHistoryRequestIdRef = useRef(0);
  const statusTimerRef = useRef(null);
  const scrapeTimerRef = useRef(null);

  const selectedParserProfile = parserProfiles.find((profile) => profile.key === formState.parserProfile) || null;
  const reviewReady = Boolean(reviewData) && !reviewStale;
  const primaryStatusTone = status.error ? "error" : reviewReady ? "ready" : "idle";
  const scrapeStatusTone = scrapeStatus.error ? "error" : scrapeResult ? "ready" : "idle";

  const writeTimedMessage = useEffectEvent((channel, baseMessage, startedAt) => {
    const message = `${baseMessage} Tempo decorrido: ${formatDuration(performance.now() - startedAt)}.`;
    if (channel === "scrape") {
      setScrapeStatus({ message, error: false });
      return;
    }
    setStatus({ message, error: false });
  });

  const stopChannelTimer = useEffectEvent((channel) => {
    const ref = channel === "scrape" ? scrapeTimerRef : statusTimerRef;
    if (ref.current) {
      window.clearInterval(ref.current.intervalId);
      ref.current = null;
    }
  });

  const startChannelTimer = useEffectEvent((channel, baseMessage) => {
    stopChannelTimer(channel);
    const startedAt = performance.now();
    writeTimedMessage(channel, baseMessage, startedAt);
    const intervalId = window.setInterval(() => {
      writeTimedMessage(channel, baseMessage, startedAt);
    }, 1000);
    const timerRef = channel === "scrape" ? scrapeTimerRef : statusTimerRef;
    timerRef.current = { intervalId, startedAt };

    return {
      elapsedMs() {
        return Math.max(0, Math.round(performance.now() - startedAt));
      },
      stop() {
        stopChannelTimer(channel);
      },
    };
  });

  useEffect(() => {
    void loadOllamaModels();
    void loadParserProfiles();
    return () => {
      if (statusTimerRef.current) {
        window.clearInterval(statusTimerRef.current.intervalId);
        statusTimerRef.current = null;
      }
      if (scrapeTimerRef.current) {
        window.clearInterval(scrapeTimerRef.current.intervalId);
        scrapeTimerRef.current = null;
      }
    };
  }, []);

  async function loadOllamaModels() {
    try {
      const response = await fetch("/providers/ollama/models");
      if (!response.ok) {
        throw new Error("Falha ao consultar os modelos locais.");
      }
      const payload = await response.json();
      setOllamaModels(Array.isArray(payload.models) ? payload.models : []);
    } catch {
      setOllamaModels([]);
    }
  }

  async function loadParserProfiles() {
    try {
      const response = await fetch("/parser/profiles");
      if (!response.ok) {
        throw new Error("Falha ao consultar os perfis do parser.");
      }
      const payload = await response.json();
      const profiles = Array.isArray(payload) ? payload : [];
      setParserProfiles(profiles);
      if (profiles.some((profile) => profile.key === "extended")) {
        setFormState((current) => ({ ...current, parserProfile: "extended" }));
      }
    } catch {
      setParserProfiles([]);
    }
  }

  function applyFormValue(name, value, options = {}) {
    const shouldMarkStale = options.markStale ?? true;
    setFormState((current) => ({ ...current, [name]: value }));
    if (shouldMarkStale) {
      markReviewAsStale();
    }
  }

  function markReviewAsStale() {
    if (!reviewData || reviewStale) {
      return;
    }
    setReviewStale(true);
    setStatus({
      message: "Os parametros mudaram. Refaca a revisao antes de gerar o relatorio final.",
      error: true,
    });
  }

  function handleFileChange(event) {
    const nextFile = event.target.files?.[0] || null;
    applyFormValue("file", nextFile, { markStale: true });
  }

  function handleTemplateChange(event) {
    const nextFile = event.target.files?.[0] || null;
    applyFormValue("templateFile", nextFile, { markStale: false });
  }

  async function handleReviewRequest(event) {
    event.preventDefault();
    if (!formState.file) {
      setStatus({ message: "Selecione uma planilha Excel valida para iniciar a analise.", error: true });
      return;
    }

    setIsLoadingReview(true);
    const timer = startChannelTimer("status", "Lendo a planilha, executando o crawler e consolidando o contexto");

    try {
      const response = await fetch("/analysis/review", {
        method: "POST",
        body: buildReviewFormData(formState),
      });

      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = await response.json();
      startTransition(() => {
        setReviewData(payload);
        setReviewStale(false);
        setGenerationHistoryState({ loading: false, error: "", items: [] });
        setHighlightGenerationId(null);
        setActiveReviewTab("overview");
      });
      await loadGenerationHistory(payload.analysis_id);
      timer.stop();
      setStatus({
        message: [
          `Analise #${payload.analysis_id} pronta`,
          payload.stats?.scrape_duration_ms != null
            ? `Crawler: ${formatDuration(payload.stats.scrape_duration_ms)}`
            : `Tempo total: ${formatDuration(timer.elapsedMs())}`,
          "Revise os blocos abaixo e so depois gere o relatorio final.",
        ].join(" | "),
        error: false,
      });
      window.setTimeout(() => {
        reviewPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 90);
    } catch (error) {
      timer.stop();
      setReviewData(null);
      setReviewStale(false);
      setGenerationHistoryState({ loading: false, error: "", items: [] });
      setStatus({
        message: error.message || "Falha ao analisar a planilha.",
        error: true,
      });
    } finally {
      timer.stop();
      setIsLoadingReview(false);
    }
  }

  async function loadGenerationHistory(analysisId, highlightId = null) {
    if (!analysisId) {
      return;
    }

    const requestId = generationHistoryRequestIdRef.current + 1;
    generationHistoryRequestIdRef.current = requestId;
    setGenerationHistoryState((current) => ({
      loading: true,
      error: "",
      items: current.items,
    }));

    try {
      const response = await fetch(`/analysis/${analysisId}/generations`);
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = await response.json();
      if (generationHistoryRequestIdRef.current !== requestId) {
        return;
      }

      startTransition(() => {
        setGenerationHistoryState({
          loading: false,
          error: "",
          items: Array.isArray(payload) ? payload : [],
        });
        setHighlightGenerationId(
          highlightId != null
            ? String(highlightId)
            : payload?.[0]?.id != null
              ? String(payload[0].id)
              : null
        );
      });
    } catch (error) {
      if (generationHistoryRequestIdRef.current !== requestId) {
        return;
      }
      setGenerationHistoryState({
        loading: false,
        error: error.message || "Nao foi possivel carregar o historico de geracao.",
        items: [],
      });
    }
  }

  async function handleGenerateReport() {
    if (!reviewData) {
      setStatus({ message: "Execute a revisao antes de gerar o relatorio final.", error: true });
      return;
    }
    if (reviewStale) {
      setStatus({
        message: "Os campos mudaram depois da ultima revisao. Refaca a analise antes de gerar.",
        error: true,
      });
      return;
    }

    setIsGenerating(true);
    const timer = startChannelTimer("status", "Compondo o relatorio e registrando a trilha da execucao");

    try {
      const response = await fetch(`/analysis/${reviewData.analysis_id}/report`, {
        method: "POST",
        body: buildGenerateFormData(formState),
      });

      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const blob = await response.blob();
      const fileName = getFileName(response) || buildFallbackName(formState.orgao, formState.outputFormat);
      const generationEventId = response.headers.get("x-generation-event-id");
      const analysisId = response.headers.get("x-analysis-id");
      const provider = response.headers.get("x-generation-provider");
      const model = response.headers.get("x-generation-model");
      const durationMs =
        parseDurationValue(response.headers.get("x-generation-duration-ms")) ?? timer.elapsedMs();

      downloadBlob(blob, fileName);
      await loadGenerationHistory(reviewData.analysis_id, generationEventId);
      timer.stop();
      setStatus({
        message: [
          `Relatorio gerado: ${fileName}`,
          analysisId ? `Analise #${analysisId}` : null,
          provider ? `Provedor: ${humanizeProvider(provider)}` : null,
          model ? `Modelo: ${model}` : null,
          `Tempo de geracao: ${formatDuration(durationMs)}`,
        ]
          .filter(Boolean)
          .join(" | "),
        error: false,
      });
    } catch (error) {
      timer.stop();
      setStatus({
        message: error.message || "Falha ao gerar o relatorio.",
        error: true,
      });
    } finally {
      timer.stop();
      setIsGenerating(false);
    }
  }

  async function handleScrape(event) {
    event.preventDefault();
    const url = formState.scrapeUrl?.trim?.() || "";
    if (!url) {
      setScrapeStatus({ message: "Informe uma URL valida para executar o crawler.", error: true });
      return;
    }

    setIsScraping(true);
    setScrapeResult(null);
    setActiveScrapeTab("links");
    const timer = startChannelTimer("scrape", "Executando o crawler sobre a origem informada");

    try {
      const query = new URLSearchParams({
        url,
        max_links: formState.scrapeMaxLinks || "40",
        crawl_depth: formState.scrapeDepth || "1",
        max_pages: formState.scrapeMaxPages || "4",
      });

      const response = await fetch(`/scrape/links?${query.toString()}`);
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = await response.json();
      const nextScrapeTab = Array.isArray(payload.links) && payload.links.length
        ? "links"
        : Array.isArray(payload.discovered_pages) && payload.discovered_pages.length
          ? "pages"
          : Array.isArray(payload.warnings) && payload.warnings.length
            ? "warnings"
            : "links";
      startTransition(() => {
        setScrapeResult(payload);
        setActiveScrapeTab(nextScrapeTab);
      });
      timer.stop();
      setScrapeStatus({
        message: `Crawler concluido em ${formatDuration(payload.processing_time_ms ?? timer.elapsedMs())}.`,
        error: false,
      });
      window.setTimeout(() => {
        scrapeResultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 90);
    } catch (error) {
      timer.stop();
      setScrapeStatus({
        message: error.message || "Falha ao executar o crawler.",
        error: true,
      });
    } finally {
      timer.stop();
      setIsScraping(false);
    }
  }

  const studioMetrics = deferredReview
    ? [
        {
          label: "Itens elegiveis",
          value: String(deferredReview.stats?.extracted_item_count ?? 0),
          icon: FileSearch,
        },
        {
          label: "Paginas rastreadas",
          value: String(deferredReview.stats?.scraped_page_count ?? 0),
          icon: Globe2,
        },
        {
          label: "Tempo do crawler",
          value: formatDuration(deferredReview.stats?.scrape_duration_ms),
          icon: TimerReset,
        },
        {
          label: "Execucoes registradas",
          value: String(generationHistoryState.items.length),
          icon: History,
        },
      ]
    : [
        { label: "Parser", value: selectedParserProfile?.label || "Estendido", icon: Filter },
        { label: "Modelos locais", value: String(ollamaModels.length), icon: Bot },
        { label: "Perfis do parser", value: String(parserProfiles.length), icon: Waypoints },
        { label: "Estado", value: reviewReady ? "Pronto" : "Aguardando revisao", icon: ShieldCheck },
      ];

  const reviewWarningCount = deferredReview?.parsed?.warnings?.length ?? 0;
  const reviewItemCount = deferredReview?.parsed?.itens_processados?.length ?? 0;
  const reviewPageCount = deferredReview?.parsed?.scraped_pages?.length ?? 0;
  const reviewHistoryCount = generationHistoryState.items.length;
  const scrapeWarningCount = scrapeResult?.warnings?.length ?? 0;
  const scrapeLinkCount = scrapeResult?.links?.length ?? 0;
  const scrapePageCount = scrapeResult?.discovered_pages?.length ?? 0;

  const reviewTabs = [
    { key: "overview", label: "Resumo", icon: Radar, count: reviewWarningCount },
    { key: "items", label: "Itens", icon: FileSearch, count: reviewItemCount },
    { key: "crawler", label: "Crawler", icon: Globe2, count: reviewPageCount },
    { key: "prompt", label: "Prompt", icon: FileText },
    { key: "history", label: "Historico", icon: History, count: reviewHistoryCount },
  ];

  const scrapeTabs = [
    { key: "links", label: "Links", icon: Link2, count: scrapeLinkCount },
    { key: "pages", label: "Paginas", icon: Globe2, count: scrapePageCount },
    { key: "warnings", label: "Alertas", icon: AlertTriangle, count: scrapeWarningCount },
  ];

  return (
    <div className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <div className="ambient ambient-c" />

      <motion.header className="hero-shell" initial="hidden" animate="visible" variants={STAGGER_VARIANTS}>
        <motion.section className="hero-panel hero-panel-main" variants={PANEL_VARIANTS}>
          <div className="hero-kicker-row">
            <span className="eyebrow">Draux Inc.</span>
            <StatusPill tone={primaryStatusTone} icon={primaryStatusTone === "error" ? AlertTriangle : Activity}>
              {primaryStatusTone === "error"
                ? "Revisao pendente"
                : reviewReady
                  ? "Pronto para gerar"
                  : "Workspace preparado"}
            </StatusPill>
          </div>

          <h1>Draux Inc. centraliza revisao, contexto web e geracao em um workspace mais comercial.</h1>
          <p className="hero-lead">
            O workspace separa com clareza configuracao, recorte, auditoria e composicao final. A
            experiencia responde melhor ao operador, reduz ambiguidade visual e deixa mais claro o
            papel de cada etapa para demonstracao e uso real.
          </p>

          <div className="hero-actions">
            <a className="primary-link" href="#workspace">
              Abrir workspace
              <ArrowRight size={18} />
            </a>
            <a className="secondary-link" href="#crawler">
              Testar crawler
              <ArrowUpRight size={18} />
            </a>
          </div>

          <div className="hero-chip-grid">
            <InsightChip icon={UploadCloud} label="Entrada auditavel" copy="Planilha, template, perfil e metadados." />
            <InsightChip icon={ScanSearch} label="Revisao guiada" copy="Itens, alertas, evidencias e prompt." />
            <InsightChip icon={BrainCircuit} label="Geracao rastreavel" copy="Provedor, modelo, fallback e duracao." />
          </div>
        </motion.section>

        <motion.aside className="hero-panel hero-panel-aside" variants={PANEL_VARIANTS}>
          <div className="dashboard-head">
            <p className="eyebrow eyebrow-soft">Resumo ao vivo</p>
            <h2>Visao executiva da operacao</h2>
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
              copy="Defina a planilha, o template opcional e o modo de composicao."
            />
            <TimelineStep
              icon={Filter}
              title="2. Recorte o parser"
              copy="Controle grupos, status e aba do checklist antes da ingestao."
            />
            <TimelineStep
              icon={Radar}
              title="3. Audite o contexto"
              copy="Valide alertas, itens, paginas, prompt e historico de execucoes."
            />
            <TimelineStep
              icon={Wand2}
              title="4. Gere o documento"
              copy="Exporte com rastreabilidade completa e tempo medido do provedor."
            />
          </div>
        </motion.aside>
      </motion.header>

      <main id="workspace" className="workspace-shell">
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

        <section className="workspace-main">
          <motion.section className="glass-panel composer-panel" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
            <div className="panel-header">
              <div>
                <span className="eyebrow">Workspace</span>
                <h2>Monte a analise antes de acionar a geracao</h2>
              </div>
              <p className="panel-copy">
                O formulario separa claramente o que entra na leitura da planilha, o que afeta a
                auditoria e o que alimenta capa e narrativa do documento final.
              </p>
            </div>

            <div className="workflow-grid">
              <GuideCard
                icon={UploadCloud}
                title="Arquivos"
                copy="A planilha alimenta a analise e o template DOCX preserva a identidade visual da entrega."
              />
              <GuideCard
                icon={Filter}
                title="Recorte"
                copy="Perfil, grupos e status controlam o que vira item elegivel na revisao e no relatorio."
              />
              <GuideCard
                icon={Sparkles}
                title="Composicao"
                copy="O modo de geracao decide se a redacao sai da IA remota, Ollama local ou regras."
              />
              <GuideCard
                icon={History}
                title="Auditoria"
                copy="Toda execucao relevante fica registrada com provedor, modelo, fallback e duracao."
              />
            </div>

            <form className="composer-form" onSubmit={handleReviewRequest}>
              <SectionCard
                number="01"
                icon={UploadCloud}
                title="Arquivos e estrategia de geracao"
                copy="Defina a entrada principal e como a composicao final deve ser feita."
              >
                <div className="field-grid field-grid-wide">
                  <FileField
                    label="Planilha Excel"
                    accept=".xlsx,.xlsm"
                    helper={describeSelectedFile(formState.file, "Nenhuma planilha selecionada.")}
                    onChange={handleFileChange}
                    required
                  />
                  <FileField
                    label="Template DOCX do relatorio"
                    accept=".docx"
                    helper={describeSelectedFile(
                      formState.templateFile,
                      "Opcional. Preserva cabecalho, rodape, logotipo e estilos."
                    )}
                    onChange={handleTemplateChange}
                  />
                </div>

                <div className="field-grid">
                  <SelectField
                    label="Formato de saida"
                    value={formState.outputFormat}
                    onChange={(event) => applyFormValue("outputFormat", event.target.value)}
                    options={OUTPUT_FORMAT_OPTIONS}
                  />
                  <SelectField
                    label="Modo de geracao"
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
                        ? `Modelos detectados: ${ollamaModels.join(", ")}`
                        : "Nenhum modelo local detectado no momento."
                    }
                    options={[
                      { value: "", label: "Selecao automatica" },
                      ...ollamaModels.map((model) => ({ value: model, label: model })),
                    ]}
                  />
                </div>
              </SectionCard>

              <SectionCard
                number="02"
                icon={Filter}
                title="Escopo do parser"
                copy="Controle o volume de itens que entram na revisao antes da composicao."
              >
                <div className="field-grid">
                  <SelectField
                    label="Perfil do parser"
                    value={formState.parserProfile}
                    onChange={(event) => applyFormValue("parserProfile", event.target.value)}
                    helper={buildParserProfileHint(selectedParserProfile)}
                    options={
                      parserProfiles.length
                        ? parserProfiles.map((profile) => ({ value: profile.key, label: profile.label }))
                        : [
                            { value: "default", label: "Padrao" },
                            { value: "extended", label: "Estendido" },
                            { value: "full", label: "Completo" },
                          ]
                    }
                  />
                  <TextField
                    label="Grupos permitidos"
                    placeholder="Ex.: 1,5 ou 1,2,3,4,5"
                    value={formState.allowedGroups}
                    onChange={(event) => applyFormValue("allowedGroups", event.target.value)}
                  />
                </div>

                <div className="field-grid">
                  <TextField
                    label="Status permitidos"
                    placeholder="Ex.: Nao,Parcialmente"
                    value={formState.allowedStatus}
                    onChange={(event) => applyFormValue("allowedStatus", event.target.value)}
                  />
                  <TextField
                    label="Nome da aba do checklist"
                    placeholder="Padrao: Checklist"
                    value={formState.checklistSheetName}
                    onChange={(event) => applyFormValue("checklistSheetName", event.target.value)}
                  />
                </div>
              </SectionCard>

              <SectionCard
                number="03"
                icon={FileText}
                title="Metadados do documento"
                copy="Esses campos nao mudam a extração do checklist, mas alimentam capa, contexto e fechamento."
              >
                <div className="field-grid">
                  <TextField
                    label="Periodo da analise"
                    placeholder="Ex.: Ciclo Q4/2025"
                    value={formState.periodoAnalise}
                    onChange={(event) => applyFormValue("periodoAnalise", event.target.value)}
                  />
                  <TextField
                    label="Numero do documento"
                    placeholder="Ex.: REP-022/2025"
                    value={formState.numeroRelatorio}
                    onChange={(event) => applyFormValue("numeroRelatorio", event.target.value)}
                  />
                </div>

                <div className="field-grid">
                  <TextField
                    label="Ticket ou solicitacao"
                    placeholder="Ex.: TASK-5492"
                    value={formState.solicitacao}
                    onChange={(event) => applyFormValue("solicitacao", event.target.value)}
                  />
                  <TextField
                    label="Area solicitante"
                    placeholder="Ex.: Operacoes, Auditoria ou PMO"
                    value={formState.requesterArea}
                    onChange={(event) => applyFormValue("requesterArea", event.target.value)}
                  />
                </div>

                <div className="field-grid">
                  <TextField
                    label="Referencia"
                    placeholder="Ex.: PROC-09.2024.00009414-6"
                    value={formState.referencia}
                    onChange={(event) => applyFormValue("referencia", event.target.value)}
                  />
                  <TextField
                    label="Documento de referencia"
                    placeholder="Ex.: DOC-145/2025"
                    value={formState.relatorioContabilReferencia}
                    onChange={(event) => applyFormValue("relatorioContabilReferencia", event.target.value)}
                  />
                </div>

                <div className="field-grid">
                  <TextField
                    label="Local de emissao"
                    placeholder="Ex.: Sao Paulo/SP"
                    value={formState.cidadeEmissao}
                    onChange={(event) => applyFormValue("cidadeEmissao", event.target.value)}
                  />
                  <TextField
                    label="Data de emissao"
                    placeholder="Ex.: 18 de dezembro de 2025"
                    value={formState.dataEmissao}
                    onChange={(event) => applyFormValue("dataEmissao", event.target.value)}
                  />
                </div>

                <div className="field-grid">
                  <TextField
                    label="Periodo de coleta"
                    placeholder="Ex.: entre 12 e 16 de dezembro de 2025"
                    value={formState.periodoColeta}
                    onChange={(event) => applyFormValue("periodoColeta", event.target.value)}
                  />
                  <TextField
                    label="Entidade"
                    placeholder="Ex.: Cliente, unidade ou organizacao analisada"
                    value={formState.orgao}
                    onChange={(event) => applyFormValue("orgao", event.target.value)}
                  />
                </div>

                <div className="field-grid">
                  <SelectField
                    label="Perfil de layout"
                    value={formState.layoutProfile}
                    onChange={(event) => applyFormValue("layoutProfile", event.target.value)}
                    options={LAYOUT_OPTIONS}
                  />
                </div>

                <TextAreaField
                  label="Equipe tecnica"
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
                    {isLoadingReview ? "Analisando..." : "Analisar contexto e evidencias"}
                  </button>
                  <button
                    className="action-button"
                    type="button"
                    disabled={!reviewReady || isGenerating}
                    onClick={handleGenerateReport}
                  >
                    {isGenerating ? "Gerando..." : "Gerar relatorio final"}
                  </button>
                </div>
              </div>
            </form>
          </motion.section>

          <AnimatePresence initial={false}>
            {deferredReview ? (
              <motion.section
                ref={reviewPanelRef}
                key="review-panel"
                className="glass-panel review-panel"
                initial={{ opacity: 0, y: 34 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              >
                <div className="panel-header">
                  <div>
                    <span className="eyebrow">Revisao auditavel</span>
                    <h2>Valide o contexto antes de exportar</h2>
                  </div>
                  <p className="panel-copy">
                    Este painel deixa explicito o papel de cada bloco: alertas, itens elegiveis,
                    evidencias de crawler, prompt de composicao e historico de execucoes. Na
                    revisao automatica, o crawler parte dos links estruturais detectados na
                    planilha: site principal, portal complementar e canal de atendimento.
                  </p>
                </div>

                <div className="workflow-grid workflow-grid-tight">
                  <GuideCard
                    icon={Radar}
                    title="Resumo e contadores"
                    copy="Apresentam o recorte lido, o volume de itens e o tempo medido do crawler."
                  />
                  <GuideCard
                    icon={AlertTriangle}
                    title="Alertas"
                    copy="Sinalizam perda de leitura, ambiguidades ou pontos que exigem revisao manual."
                  />
                  <GuideCard
                    icon={FileSearch}
                    title="Itens elegiveis"
                    copy="Sao a base estruturada da composicao. Se estiverem errados, a geracao sai errada."
                  />
                  <GuideCard
                    icon={Globe2}
                    title="Evidencias"
                    copy="Contextualizam a analise com paginas rastreadas, links priorizados e profundidade."
                  />
                </div>

                <div className="stats-grid">
                  <MetricCard icon={FileSearch} label="Analise" value={`#${deferredReview.analysis_id}`} />
                  <MetricCard
                    icon={Filter}
                    label="Perfil"
                    value={humanizeParserProfile(
                      deferredReview.parsed?.parser_options?.profile,
                      deferredReview.parsed?.parser_options?.profile
                    )}
                  />
                  <MetricCard
                    icon={Waypoints}
                    label="Grupos"
                    value={(deferredReview.parsed?.parser_options?.allowed_groups || []).join(", ") || "-"}
                  />
                  <MetricCard
                    icon={AlertTriangle}
                    label="Status"
                    value={(deferredReview.parsed?.parser_options?.allowed_status || []).join(", ") || "-"}
                  />
                  <MetricCard
                    icon={FileSpreadsheet}
                    label="Itens elegiveis"
                    value={String(deferredReview.stats?.extracted_item_count ?? 0)}
                  />
                  <MetricCard
                    icon={Globe2}
                    label="Paginas rastreadas"
                    value={String(deferredReview.stats?.scraped_page_count ?? 0)}
                  />
                  <MetricCard
                    icon={Link2}
                    label="Links rastreados"
                    value={String(deferredReview.stats?.scraped_link_count ?? 0)}
                  />
                  <MetricCard
                    icon={Clock3}
                    label="Tempo do crawler"
                    value={formatDuration(deferredReview.stats?.scrape_duration_ms)}
                  />
                </div>

                <div className="panel-navigator">
                  <div>
                    <span className="eyebrow eyebrow-soft">Navegacao por contexto</span>
                    <p className="navigator-copy">
                      Use as abas para revisar cada camada sem expandir todo o painel de uma vez.
                    </p>
                  </div>
                  <TabStrip tabs={reviewTabs} activeKey={activeReviewTab} onChange={setActiveReviewTab} />
                </div>

                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={activeReviewTab}
                    className="tab-panel"
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 12 }}
                    transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                  >
                    {activeReviewTab === "overview" ? (
                      <div className="review-stack">
                        <ReviewSection
                          title="Alertas do parser e da ingestao"
                          subtitle="Pontos que merecem revisao manual antes da composicao."
                        >
                          {Array.isArray(deferredReview.parsed?.warnings) && deferredReview.parsed.warnings.length ? (
                            <ul className="list-block">
                              {deferredReview.parsed.warnings.map((warning, index) => (
                                <li key={`${warning}-${index}`}>{warning}</li>
                              ))}
                            </ul>
                          ) : (
                            <EmptyBlock message="Nenhum alerta de leitura foi registrado nesta analise." />
                          )}
                        </ReviewSection>

                        <ReviewSection
                          title="Resumo consolidado da analise"
                          subtitle="Sintese textual do contexto consolidado antes da composicao."
                        >
                          <PreBlock text={deferredReview.summary || "Sem resumo consolidado."} />
                        </ReviewSection>
                      </div>
                    ) : null}

                    {activeReviewTab === "items" ? (
                      <ReviewSection
                        title="Itens elegiveis para o relatorio"
                        subtitle="Base principal usada pelo sistema para construir as secoes do documento."
                      >
                        {Array.isArray(deferredReview.parsed?.itens_processados) &&
                        deferredReview.parsed.itens_processados.length ? (
                          <div className="card-grid">
                            {deferredReview.parsed.itens_processados.map((item) => (
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
                                {Array.isArray(item.detalhes) && item.detalhes.length ? (
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
                          <EmptyBlock message="Nenhum item elegivel apareceu no recorte atual. Amplie perfil, grupos ou status se precisar." />
                        )}
                      </ReviewSection>
                    ) : null}

                    {activeReviewTab === "crawler" ? (
                      <ReviewSection
                        title="Paginas e evidencias rastreadas"
                        subtitle="Apoio contextual coletado pelo crawler para enriquecer a leitura."
                      >
                        {Array.isArray(deferredReview.parsed?.scraped_pages) &&
                        deferredReview.parsed.scraped_pages.length ? (
                          <div className="card-grid">
                            {deferredReview.parsed.scraped_pages.map((page, index) => (
                              <article key={`${page.final_url}-${index}`} className="data-card">
                                <div className="card-head">
                                  <div>
                                    <h3>{page.page_title || "Pagina sem titulo"}</h3>
                                    <p className="meta-line">{humanizeSource(page.fonte)}</p>
                                  </div>
                                  <StatusPill tone="neutral" icon={Globe2}>
                                    {Array.isArray(page.links) ? `${page.links.length} link(s)` : "0 link"}
                                  </StatusPill>
                                </div>
                                <p className="body-copy">{page.summary}</p>
                                <p className="meta-line">
                                  {page.final_url} | Profundidade: {page.discovery_depth ?? 0}
                                  {page.discovered_from_label ? ` | Via: ${page.discovered_from_label}` : ""}
                                  {typeof page.page_score === "number" && page.page_score > 0
                                    ? ` | Pontuacao: ${page.page_score}`
                                    : ""}
                                </p>
                                {(page.links || []).slice(0, 4).length ? (
                                  <ul className="detail-list">
                                    {(page.links || []).slice(0, 4).map((link, linkIndex) => (
                                      <li key={`${page.final_url}-link-${linkIndex}`}>
                                        {humanizeCategory(link.category)}: {link.label || link.url}
                                        {typeof link.score === "number" ? ` | Pontuacao ${link.score}` : ""}
                                        {link.evidence_summary ? ` | ${link.evidence_summary}` : ""}
                                      </li>
                                    ))}
                                  </ul>
                                ) : null}
                              </article>
                            ))}
                          </div>
                        ) : (
                          <EmptyBlock message="Nenhuma pagina foi rastreada nesta analise. O relatorio seguira apenas com checklist e metadados." />
                        )}
                      </ReviewSection>
                    ) : null}

                    {activeReviewTab === "prompt" ? (
                      <div className="review-stack">
                        <ReviewSection
                          title="Previa do prompt de composicao"
                          subtitle="Permite auditar as instrucoes repassadas para a geracao do texto."
                        >
                          <PreBlock text={deferredReview.prompt_preview || "Sem prompt disponivel."} />
                        </ReviewSection>

                        <article className="summary-card">
                          <div className="card-head">
                            <div>
                              <h3>Configuracao ativa da geracao</h3>
                              <p className="meta-line">Referencia rapida do modo de saida que sera aplicado ao exportar.</p>
                            </div>
                            <StatusPill tone="neutral" icon={Sparkles}>
                              Composicao atual
                            </StatusPill>
                          </div>
                          <div className="trace-badges">
                            <Tag icon={Sparkles}>{humanizeGenerationMode(formState.generationMode)}</Tag>
                            <Tag icon={FileText}>{(formState.outputFormat || "docx").toUpperCase()}</Tag>
                            <Tag icon={Bot}>{formState.localModel || "Selecao automatica"}</Tag>
                          </div>
                        </article>
                      </div>
                    ) : null}

                    {activeReviewTab === "history" ? (
                      <ReviewSection
                        title="Historico de geracao e auditoria"
                        subtitle="Rastro completo de provedor, modelo, fallback, tempo e payload salvo."
                      >
                        {generationHistoryState.loading ? (
                          <EmptyBlock message="Consultando execucoes registradas..." />
                        ) : generationHistoryState.error ? (
                          <EmptyBlock message={generationHistoryState.error} tone="error" />
                        ) : generationHistoryState.items.length ? (
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
                        ) : (
                          <EmptyBlock message="Nenhuma execucao foi registrada ainda para esta analise." />
                        )}
                      </ReviewSection>
                    ) : null}
                  </motion.div>
                </AnimatePresence>
              </motion.section>
            ) : null}
          </AnimatePresence>

          <motion.section
            id="crawler"
            className="glass-panel crawler-panel"
            initial="hidden"
            animate="visible"
            variants={PANEL_VARIANTS}
          >
            <div className="panel-header">
              <div>
                <span className="eyebrow">Crawler isolado</span>
                <h2>Teste uma origem antes de acopla-la ao fluxo principal</h2>
              </div>
              <p className="panel-copy">
                Use este modulo para entender como o crawler classifica links, navega paginas
                relacionadas e mede o tempo de processamento fora da revisao completa. No fluxo
                principal, links referenciais fora do mapeamento estrutural da planilha ainda nao
                entram automaticamente como semente do scan.
              </p>
            </div>

            <div className="workflow-grid workflow-grid-tight">
              <GuideCard
                icon={Link2}
                title="Maximo de links"
                copy="Limita quantos links da pagina inicial entram no ranking retornado."
              />
              <GuideCard
                icon={Waypoints}
                title="Profundidade"
                copy="Controla quantos niveis de navegação o crawler percorre alem da origem."
              />
              <GuideCard
                icon={Globe2}
                title="Paginas descobertas"
                copy="Define quantas paginas adicionais podem ser abertas para contextualizacao."
              />
              <GuideCard
                icon={TimerReset}
                title="Tempo do processamento"
                copy="Explicita a duracao do crawler para facilitar comparacao entre parametros."
              />
            </div>

            <form className="composer-form" onSubmit={handleScrape}>
              <div className="field-grid">
                <TextField
                  label="URL da pagina"
                  type="url"
                  placeholder="Ex.: https://example.com/"
                  value={formState.scrapeUrl || ""}
                  onChange={(event) => applyFormValue("scrapeUrl", event.target.value, { markStale: false })}
                  required
                />
                <TextField
                  label="Maximo de links"
                  type="number"
                  min="1"
                  max="200"
                  value={formState.scrapeMaxLinks || "40"}
                  onChange={(event) => applyFormValue("scrapeMaxLinks", event.target.value, { markStale: false })}
                />
              </div>

              <div className="field-grid">
                <TextField
                  label="Profundidade do crawl"
                  type="number"
                  min="0"
                  max="3"
                  value={formState.scrapeDepth || "1"}
                  onChange={(event) => applyFormValue("scrapeDepth", event.target.value, { markStale: false })}
                />
                <TextField
                  label="Maximo de paginas descobertas"
                  type="number"
                  min="0"
                  max="20"
                  value={formState.scrapeMaxPages || "4"}
                  onChange={(event) => applyFormValue("scrapeMaxPages", event.target.value, { markStale: false })}
                />
              </div>

              <div className="action-bar action-bar-secondary">
                <div className="action-copy">
                  <span className="eyebrow eyebrow-soft">Status do crawler</span>
                  <StatusBlock tone={scrapeStatusTone} message={scrapeStatus.message} compact />
                </div>
                <div className="action-buttons">
                  <button className="action-button" type="submit" disabled={isScraping}>
                    {isScraping ? "Executando..." : "Executar crawler"}
                  </button>
                </div>
              </div>
            </form>

            <AnimatePresence initial={false}>
              {scrapeResult ? (
                <motion.div
                  ref={scrapeResultRef}
                  key="scrape-result"
                  className="scrape-result"
                  initial={{ opacity: 0, y: 26 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 16 }}
                  transition={{ duration: 0.32 }}
                >
                  <article className="summary-card">
                    <div className="card-head">
                      <div>
                        <h3>{scrapeResult.page_title || "Pagina inicial analisada"}</h3>
                        <p className="meta-line">
                          URL final: {scrapeResult.final_url}
                          {scrapeResult.processing_time_ms != null
                            ? ` | Tempo: ${formatDuration(scrapeResult.processing_time_ms)}`
                            : ""}
                          {Array.isArray(scrapeResult.discovered_pages) && scrapeResult.discovered_pages.length
                            ? ` | ${scrapeResult.discovered_pages.length} pagina(s) descoberta(s)`
                            : ""}
                        </p>
                      </div>
                      <StatusPill tone="ready" icon={ScanSearch}>
                        Crawler concluido
                      </StatusPill>
                    </div>
                    <p className="body-copy">{scrapeResult.summary}</p>
                  </article>

                  <div className="panel-navigator panel-navigator-compact">
                    <div>
                      <span className="eyebrow eyebrow-soft">Saida organizada</span>
                      <p className="navigator-copy">
                        Alterne entre links, paginas e alertas para inspecionar o crawl com menos ruido visual.
                      </p>
                    </div>
                    <TabStrip tabs={scrapeTabs} activeKey={activeScrapeTab} onChange={setActiveScrapeTab} />
                  </div>

                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                      key={activeScrapeTab}
                      className="tab-panel"
                      initial={{ opacity: 0, y: 18 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 12 }}
                      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                    >
                      {activeScrapeTab === "warnings" ? (
                        Array.isArray(scrapeResult.warnings) && scrapeResult.warnings.length ? (
                          <article className="summary-card summary-card-warning">
                            <h3>Alertas do crawler</h3>
                            <ul className="list-block">
                              {scrapeResult.warnings.map((warning, index) => (
                                <li key={`scrape-warning-${index}`}>{warning}</li>
                              ))}
                            </ul>
                          </article>
                        ) : (
                          <EmptyBlock message="Nenhum alerta foi registrado para esta execucao do crawler." />
                        )
                      ) : null}

                      {activeScrapeTab === "links" ? (
                        Array.isArray(scrapeResult.links) && scrapeResult.links.length ? (
                          <div className="card-grid">
                            {scrapeResult.links.map((link, index) => (
                              <article key={`${link.url}-${index}`} className="data-card">
                                <div className="card-head">
                                  <div>
                                    <h3>{link.label || link.url}</h3>
                                    <p className="meta-line">{humanizeCategory(link.category)}</p>
                                  </div>
                                  <StatusPill tone="neutral" icon={Link2}>
                                    {humanizeDestination(link.destination_type)}
                                  </StatusPill>
                                </div>
                                <a className="inline-link" href={link.url} target="_blank" rel="noreferrer">
                                  {link.url}
                                  <ArrowUpRight size={14} />
                                </a>
                                <p className="meta-line">
                                  {link.section ? `Secao: ${link.section} | ` : ""}
                                  {link.is_internal ? "Link interno" : "Link externo"}
                                  {typeof link.score === "number" ? ` | Pontuacao: ${link.score}` : ""}
                                </p>
                                {link.context ? <p className="body-copy">{link.context}</p> : null}
                                {link.evidence_summary ? <p className="body-copy strong-copy">{link.evidence_summary}</p> : null}
                              </article>
                            ))}
                          </div>
                        ) : (
                          <EmptyBlock message="Nenhum link priorizado foi retornado para os parametros usados." />
                        )
                      ) : null}

                      {activeScrapeTab === "pages" ? (
                        Array.isArray(scrapeResult.discovered_pages) && scrapeResult.discovered_pages.length ? (
                          <div className="card-grid">
                            {scrapeResult.discovered_pages.map((page, index) => (
                              <article key={`${page.final_url}-${index}`} className="data-card">
                                <div className="card-head">
                                  <div>
                                    <h3>{page.page_title || page.final_url}</h3>
                                    <p className="meta-line">Pagina descoberta</p>
                                  </div>
                                  <StatusPill tone="neutral" icon={Globe2}>
                                    Profundidade {page.discovery_depth ?? 0}
                                  </StatusPill>
                                </div>
                                <p className="meta-line">
                                  {typeof page.page_score === "number" && page.page_score > 0
                                    ? `Pontuacao: ${page.page_score}`
                                    : "Pontuacao nao informada"}
                                  {page.discovered_from_label ? ` | Via: ${page.discovered_from_label}` : ""}
                                </p>
                                <p className="body-copy">{page.summary}</p>
                              </article>
                            ))}
                          </div>
                        ) : (
                          <EmptyBlock message="Nenhuma pagina adicional foi descoberta com a profundidade atual." />
                        )
                      ) : null}
                    </motion.div>
                  </AnimatePresence>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </motion.section>
        </section>
      </main>
    </div>
  );
}

function PanelTitle({ icon: Icon, kicker, title }) {
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

function StatusBlock({ tone, message, compact = false }) {
  return <p className={`status-block status-${tone} ${compact ? "status-compact" : ""}`}>{message}</p>;
}

function StatusPill({ tone, icon: Icon, children }) {
  return (
    <span className={`status-pill status-pill-${tone}`}>
      {Icon ? <Icon size={14} /> : null}
      {children}
    </span>
  );
}

function InsightChip({ icon: Icon, label, copy }) {
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

function TimelineStep({ icon: Icon, title, copy }) {
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

function MetricCard({ icon: Icon, label, value }) {
  return (
    <div className="metric-card">
      <div className="metric-label">
        <span className="icon-badge icon-badge-soft">
          <Icon size={16} />
        </span>
        <span>{label}</span>
      </div>
      <strong>{value || "-"}</strong>
    </div>
  );
}

function GuideCard({ icon: Icon, title, copy }) {
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

function TabStrip({ tabs, activeKey, onChange }) {
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

function SectionCard({ number, icon: Icon, title, copy, children }) {
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

function FieldFrame({ label, helper, children }) {
  return (
    <label className="field-frame">
      <span className="field-label">{label}</span>
      {children}
      {helper ? <small className="field-helper">{helper}</small> : null}
    </label>
  );
}

function TextField({ label, helper, ...props }) {
  return (
    <FieldFrame label={label} helper={helper}>
      <input {...props} />
    </FieldFrame>
  );
}

function SelectField({ label, helper, options, ...props }) {
  return (
    <FieldFrame label={label} helper={helper}>
      <select {...props}>
        {options.map((option) => (
          <option key={`${label}-${option.value}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldFrame>
  );
}

function TextAreaField({ label, helper, ...props }) {
  return (
    <FieldFrame label={label} helper={helper}>
      <textarea {...props} />
    </FieldFrame>
  );
}

function FileField({ label, helper, ...props }) {
  return (
    <FieldFrame label={label} helper={helper}>
      <div className="file-shell">
        <UploadCloud size={18} />
        <input {...props} type="file" />
      </div>
    </FieldFrame>
  );
}

function ReviewSection({ title, subtitle, children }) {
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

function EmptyBlock({ message, tone = "neutral" }) {
  return <div className={`empty-block empty-${tone}`}>{message}</div>;
}

function PreBlock({ text }) {
  return <pre className="pre-block">{text}</pre>;
}

function TraceCard({ trace, isHighlighted }) {
  return (
    <article className={`trace-card ${isHighlighted ? "trace-card-highlighted" : ""}`}>
      <div className="card-head">
        <div>
          <h3>Execucao #{trace.id || "-"}</h3>
          <p className="meta-line">{formatGenerationDate(trace.created_at) || "Data nao registrada"}</p>
        </div>
        {isHighlighted ? (
          <StatusPill tone="ready" icon={CheckCircle2}>
            Ultima execucao
          </StatusPill>
        ) : null}
      </div>

      <p className="meta-line">
        Solicitado: {humanizeGenerationMode(trace.requested_mode)} | Executado:{" "}
        {humanizeGenerationMode(trace.used_mode)} | Saida: {(trace.output_format || "docx").toUpperCase()}
        {trace.duration_ms != null ? ` | Tempo: ${formatDuration(trace.duration_ms)}` : ""}
      </p>

      <div className="trace-badges">
        <Tag icon={Bot}>{humanizeProvider(trace.provider)}</Tag>
        {trace.model_name ? <Tag icon={BrainCircuit}>{trace.model_name}</Tag> : null}
        {trace.fallback_reason ? <Tag icon={AlertTriangle}>Fallback registrado</Tag> : null}
      </div>

      {trace.fallback_reason ? <p className="body-copy">{trace.fallback_reason}</p> : null}

      {trace.prompt_snapshot ? (
        <details className="trace-details">
          <summary>Prompt salvo</summary>
          <PreBlock text={trace.prompt_snapshot} />
        </details>
      ) : null}

      {trace.raw_response ? (
        <details className="trace-details">
          <summary>Resposta bruta</summary>
          <PreBlock text={trace.raw_response} />
        </details>
      ) : null}
    </article>
  );
}

function Tag({ icon: Icon, children }) {
  return (
    <span className="tag">
      {Icon ? <Icon size={12} /> : null}
      {children}
    </span>
  );
}

function buildReviewFormData(formState) {
  const formData = new FormData();
  formData.append("file", formState.file);
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

function buildGenerateFormData(formState) {
  const formData = new FormData();
  if (formState.templateFile) {
    formData.append("template_file", formState.templateFile);
  }
  appendFormValue(formData, "output_format", formState.outputFormat || "docx");
  appendFormValue(formData, "generation_mode", formState.generationMode || "auto");
  appendFormValue(formData, "local_model", formState.localModel);
  return formData;
}

function appendFormValue(formData, key, value) {
  if (value == null) {
    return;
  }
  if (typeof value === "string" && value.trim() === "") {
    return;
  }
  formData.append(key, value);
}

async function extractError(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json();
    return payload.detail || "Falha na operacao.";
  }
  const text = await response.text();
  return text || "Falha na operacao.";
}

function getFileName(response) {
  const header = response.headers.get("content-disposition");
  if (!header) {
    return null;
  }
  const match = header.match(/filename=\"?([^"]+)\"?/i);
  return match ? match[1] : null;
}

function buildFallbackName(entityName, outputFormat) {
  const base = entityName || "relatorio-tecnico";
  const slug = base
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
  return `${slug || "relatorio-tecnico"}.${outputFormat || "docx"}`;
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

function describeSelectedFile(file, fallback) {
  if (!file) {
    return fallback;
  }
  return `${file.name} | ${Math.max(1, Math.round(file.size / 1024))} KB`;
}

function buildParserProfileHint(profile) {
  if (!profile) {
    return "O backend aplica o perfil escolhido antes de extrair os itens elegiveis.";
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

function humanizeParserProfile(profileKey, fallback) {
  const labels = {
    default: "Padrao",
    extended: "Estendido",
    full: "Completo",
  };
  return labels[profileKey] || fallback || profileKey || "Padrao";
}

function humanizeSource(source) {
  return SOURCE_LABELS[source] || source || "Fonte nao identificada";
}

function humanizeCategory(category) {
  return CATEGORY_LABELS[category] || category || "Outros";
}

function humanizeDestination(destination) {
  return DESTINATION_LABELS[destination] || destination || "Pagina";
}

function humanizeGenerationMode(mode) {
  return GENERATION_MODE_LABELS[mode] || mode || "Nao informado";
}

function humanizeProvider(provider) {
  return PROVIDER_LABELS[provider] || provider || "Nao informado";
}

function humanizeStatusTone(status) {
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

function formatGenerationDate(value) {
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

function formatDuration(value) {
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

function parseDurationValue(value) {
  if (value == null || value === "") {
    return null;
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue < 0) {
    return null;
  }
  return Math.round(numericValue);
}
