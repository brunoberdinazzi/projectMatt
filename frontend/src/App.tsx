import {
  Suspense,
  lazy,
  startTransition,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";
import type { ChangeEvent, FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Bot,
  FileSearch,
  Filter,
  Globe2,
  History,
  ShieldCheck,
  TimerReset,
  Waypoints,
} from "lucide-react";
import {
  buildFallbackName,
  buildGenerateFormData,
  buildReviewFormData,
  describeParseOrigin,
  downloadBlob,
  extractError,
  formatDuration,
  formatStoredSheetSelection,
  getFileName,
  humanizeProvider,
  inferLayoutProfile,
  INITIAL_FORM_STATE,
  parseDurationValue,
} from "./lib/app-utils";
import { MarketingAuthShell } from "./components/marketing-auth-shell";
import { WorkspaceHero } from "./components/workspace-hero";
import { WorkspaceHub, WorkspaceUtilityModal } from "./components/workspace-organizer";
import type {
  AccountPasswordField,
  AccountPasswordForm,
  AccountProfileField,
  AccountProfileForm,
  ActiveReviewTab,
  ActiveUtilityModal,
  ActiveWorkspaceTab,
  AnalysisReviewResponse,
  AsyncDataState,
  AsyncItemsState,
  AuthPasswordForgotResponse,
  FinancialAliasCatalogResponse,
  FinancialAliasItem,
  FinancialAliasKind,
  AuthSessionResponse,
  ForgotPasswordForm,
  GenerationTraceItem,
  LoginForm,
  OllamaModelsResponse,
  OllamaStatusResponse,
  ParserDetectionState,
  ParserProfileDefinition,
  RegisterForm,
  ResetPasswordForm,
  ScrapePageResult,
  SessionState,
  StatusFeedback,
  StatusTone,
  StoredAnalysisListItem,
  TabDescriptor,
  WorkspaceMetric,
  ChecklistParseResult,
  AuthUser,
} from "./types/workspace";

const ComposerPanel = lazy(() =>
  import("./components/composer-panel").then((module) => ({ default: module.ComposerPanel }))
);
const CrawlerPanel = lazy(() =>
  import("./components/crawler-panel").then((module) => ({ default: module.CrawlerPanel }))
);
const ReviewPanel = lazy(() =>
  import("./components/review-panel").then((module) => ({ default: module.ReviewPanel }))
);

type AuthMode = "login" | "register" | "forgot" | "reset";
type WorkspaceChannel = "status" | "scrape";
type ActiveScrapeTab = "links" | "pages" | "warnings";

interface TimerState {
  intervalId: number;
  startedAt: number;
}

interface ChannelTimer {
  elapsedMs(): number;
  stop(): void;
}

const DEFAULT_STATUS: StatusFeedback = {
  message: "Preencha os campos e execute a revisão para liberar a geração final.",
  error: false,
};

const DEFAULT_SCRAPE_STATUS: StatusFeedback = {
  message: "Informe uma URL e execute o crawler para inspecionar a origem manualmente.",
  error: false,
};

function toErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

interface WorkspaceStageLoaderProps {
  tabKey: ActiveWorkspaceTab | string;
}

function WorkspaceStageLoader({ tabKey }: WorkspaceStageLoaderProps) {
  const titleMap: Record<ActiveWorkspaceTab, string> = {
    composer: "Carregando configuração",
    review: "Carregando revisão",
    crawler: "Carregando crawler",
  };

  return (
    <section className="glass-panel workspace-placeholder">
      <span className="eyebrow">Draux Inc.</span>
      <h2>{titleMap[tabKey as ActiveWorkspaceTab] || "Carregando workspace"}</h2>
      <p className="body-copy">
        Estamos preparando a etapa selecionada com carregamento sob demanda para deixar a abertura mais leve.
      </p>
    </section>
  );
}

export default function App() {
  const [sessionState, setSessionState] = useState<SessionState>({
    loading: true,
    user: null,
    session: null,
    error: "",
  });
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [authFeedback, setAuthFeedback] = useState<StatusFeedback>({ message: "", error: false });
  const [isSubmittingAuth, setIsSubmittingAuth] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isBootstrappingWorkspace, setIsBootstrappingWorkspace] = useState(false);
  const [loginForm, setLoginForm] = useState<LoginForm>({
    email: "",
    password: "",
  });
  const [registerForm, setRegisterForm] = useState<RegisterForm>({
    fullName: "",
    email: "",
    password: "",
  });
  const [forgotPasswordForm, setForgotPasswordForm] = useState<ForgotPasswordForm>({
    email: "",
  });
  const [resetPasswordForm, setResetPasswordForm] = useState<ResetPasswordForm>({
    token: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [accountProfileForm, setAccountProfileForm] = useState<AccountProfileForm>({
    fullName: "",
    email: "",
  });
  const [accountPasswordForm, setAccountPasswordForm] = useState<AccountPasswordForm>({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [accountProfileFeedback, setAccountProfileFeedback] = useState<StatusFeedback>({ message: "", error: false });
  const [accountPasswordFeedback, setAccountPasswordFeedback] = useState<StatusFeedback>({ message: "", error: false });
  const [isSavingAccountProfile, setIsSavingAccountProfile] = useState(false);
  const [isSavingAccountPassword, setIsSavingAccountPassword] = useState(false);
  const [formState, setFormState] = useState(INITIAL_FORM_STATE);
  const [status, setStatus] = useState(DEFAULT_STATUS);
  const [scrapeStatus, setScrapeStatus] = useState(DEFAULT_SCRAPE_STATUS);
  const [reviewData, setReviewData] = useState<AnalysisReviewResponse | null>(null);
  const [reviewStale, setReviewStale] = useState(false);
  const [generationHistoryState, setGenerationHistoryState] = useState<AsyncItemsState<GenerationTraceItem>>({
    loading: false,
    error: "",
    items: [],
  });
  const [recentAnalysesState, setRecentAnalysesState] = useState<AsyncItemsState<StoredAnalysisListItem>>({
    loading: false,
    error: "",
    items: [],
  });
  const [highlightGenerationId, setHighlightGenerationId] = useState<string | null>(null);
  const [scrapeResult, setScrapeResult] = useState<ScrapePageResult | null>(null);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [recommendedLocalModel, setRecommendedLocalModel] = useState("");
  const [ollamaStatusState, setOllamaStatusState] = useState<AsyncDataState<OllamaStatusResponse>>({
    loading: false,
    error: "",
    data: null,
  });
  const [parserProfiles, setParserProfiles] = useState<ParserProfileDefinition[]>([]);
  const [parserDetectionState, setParserDetectionState] = useState<ParserDetectionState>({
    loading: false,
    error: "",
    data: null,
  });
  const [isLoadingReview, setIsLoadingReview] = useState(false);
  const [isLoadingStoredAnalysis, setIsLoadingStoredAnalysis] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isScraping, setIsScraping] = useState(false);
  const [activeReviewTab, setActiveReviewTab] = useState<ActiveReviewTab>("overview");
  const [activeScrapeTab, setActiveScrapeTab] = useState<ActiveScrapeTab>("links");
  const [activeWorkspaceTab, setActiveWorkspaceTab] = useState<ActiveWorkspaceTab>("composer");
  const [activeUtilityModal, setActiveUtilityModal] = useState<ActiveUtilityModal | null>(null);
  const [savedAnalysisId, setSavedAnalysisId] = useState("");
  const [financialAliasesState, setFinancialAliasesState] = useState<AsyncDataState<FinancialAliasCatalogResponse>>({
    loading: false,
    error: "",
    data: null,
  });
  const [aliasDrafts, setAliasDrafts] = useState<Record<string, string>>({});
  const [aliasBusyKey, setAliasBusyKey] = useState<string | null>(null);
  const [aliasFeedback, setAliasFeedback] = useState<StatusFeedback>({ message: "", error: false });

  const deferredReview = useDeferredValue(reviewData);
  const reviewPanelRef = useRef<HTMLElement | null>(null);
  const scrapeResultRef = useRef<HTMLElement | null>(null);
  const generationHistoryRequestIdRef = useRef(0);
  const parserDetectionRequestIdRef = useRef(0);
  const statusTimerRef = useRef<TimerState | null>(null);
  const scrapeTimerRef = useRef<TimerState | null>(null);

  const selectedParserProfile = parserProfiles.find((profile) => profile.key === formState.parserProfile) || null;
  const selectedWorkbook = formState.files[0] || formState.file;
  const detectedParserProfile =
    parserProfiles.find((profile) => profile.key === parserDetectionState.data?.resolved_profile) || null;
  const activeParserProfile =
    formState.parserProfile === "auto" ? detectedParserProfile || selectedParserProfile : selectedParserProfile;
  const reviewReady = Boolean(reviewData) && !reviewStale;
  const primaryStatusTone: StatusTone = status.error ? "error" : reviewReady ? "ready" : "idle";
  const scrapeStatusTone: StatusTone = scrapeStatus.error ? "error" : scrapeResult ? "ready" : "idle";
  const userInitials = String(sessionState.user?.full_name || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");

  const writeTimedMessage = useEffectEvent((channel: WorkspaceChannel, baseMessage: string, startedAt: number) => {
    const message = `${baseMessage} Tempo decorrido: ${formatDuration(performance.now() - startedAt)}.`;
    if (channel === "scrape") {
      setScrapeStatus({ message, error: false });
      return;
    }
    setStatus({ message, error: false });
  });

  const stopChannelTimer = useEffectEvent((channel: WorkspaceChannel) => {
    const ref = channel === "scrape" ? scrapeTimerRef : statusTimerRef;
    if (ref.current) {
      window.clearInterval(ref.current.intervalId);
      ref.current = null;
    }
  });

  const startChannelTimer = useEffectEvent((channel: WorkspaceChannel, baseMessage: string): ChannelTimer => {
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

  const resetWorkspaceState = useEffectEvent(() => {
    stopChannelTimer("status");
    stopChannelTimer("scrape");
    setFormState({ ...INITIAL_FORM_STATE });
    setStatus(DEFAULT_STATUS);
    setScrapeStatus(DEFAULT_SCRAPE_STATUS);
    setReviewData(null);
    setReviewStale(false);
    setGenerationHistoryState({ loading: false, error: "", items: [] });
    setRecentAnalysesState({ loading: false, error: "", items: [] });
    setHighlightGenerationId(null);
    setScrapeResult(null);
    setOllamaModels([]);
    setRecommendedLocalModel("");
    setOllamaStatusState({ loading: false, error: "", data: null });
    setParserProfiles([]);
    setParserDetectionState({ loading: false, error: "", data: null });
    setIsBootstrappingWorkspace(false);
    setIsLoadingReview(false);
    setIsLoadingStoredAnalysis(false);
    setIsGenerating(false);
    setIsScraping(false);
    setActiveReviewTab("overview");
    setActiveScrapeTab("links");
    setActiveWorkspaceTab("composer");
    setActiveUtilityModal(null);
    setSavedAnalysisId("");
    setFinancialAliasesState({ loading: false, error: "", data: null });
    setAliasDrafts({});
    setAliasBusyKey(null);
    setAliasFeedback({ message: "", error: false });
    setAccountProfileForm({ fullName: "", email: "" });
    setAccountPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
    setForgotPasswordForm({ email: "" });
    setResetPasswordForm({ token: "", newPassword: "", confirmPassword: "" });
    setAccountProfileFeedback({ message: "", error: false });
    setAccountPasswordFeedback({ message: "", error: false });
    setIsSavingAccountProfile(false);
    setIsSavingAccountPassword(false);
  });

  useEffect(() => {
    void loadSession();
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

  useEffect(() => {
    if (!sessionState.loading && sessionState.user) {
      void bootstrapAuthenticatedWorkspace();
    }
  }, [sessionState.loading, sessionState.user?.id]);

  useEffect(() => {
    if (!selectedWorkbook) {
      parserDetectionRequestIdRef.current += 1;
      setParserDetectionState({ loading: false, error: "", data: null });
      return;
    }

    if (formState.parserProfile !== "auto") {
      parserDetectionRequestIdRef.current += 1;
      setParserDetectionState({ loading: false, error: "", data: null });
      return;
    }

    void detectParserProfile(selectedWorkbook);
  }, [selectedWorkbook, formState.parserProfile]);

  useEffect(() => {
    if (!sessionState.user) {
      setAccountProfileForm({ fullName: "", email: "" });
      setAccountPasswordForm({ currentPassword: "", newPassword: "", confirmPassword: "" });
      setAccountProfileFeedback({ message: "", error: false });
      setAccountPasswordFeedback({ message: "", error: false });
      return;
    }

    setAccountProfileForm({
      fullName: sessionState.user.full_name || "",
      email: sessionState.user.email || "",
    });
  }, [sessionState.user?.id, sessionState.user?.full_name, sessionState.user?.email]);

  useEffect(() => {
    if (!sessionState.user || activeUtilityModal !== "aliases") {
      return;
    }
    void loadFinancialAliases();
  }, [activeUtilityModal, sessionState.user?.id]);

  useEffect(() => {
    if (activeUtilityModal === "aliases") {
      return;
    }
    setAliasBusyKey(null);
    setAliasFeedback({ message: "", error: false });
  }, [activeUtilityModal]);

  async function loadSession(): Promise<void> {
    setSessionState((current) => ({
      ...current,
      loading: true,
      error: "",
    }));

    try {
      const response = await fetch("/auth/me");
      if (response.status === 401) {
        setSessionState({
          loading: false,
          user: null,
          session: null,
          error: "",
        });
        return;
      }
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as AuthSessionResponse;
      setSessionState({
        loading: false,
        user: payload.user || null,
        session: payload.session || null,
        error: "",
      });
      setAuthFeedback({ message: "", error: false });
    } catch (error) {
      setSessionState({
        loading: false,
        user: null,
        session: null,
        error: toErrorMessage(error, "Não foi possível verificar a sessão atual."),
      });
    }
  }

  async function fetchProtected(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const response = await fetch(input, init);
    if (response.status === 401) {
      resetWorkspaceState();
      setSessionState({
        loading: false,
        user: null,
        session: null,
        error: "",
      });
      setAuthMode("login");
      setAuthFeedback({
        message: "Sua sessão expirou. Entre novamente para continuar usando a plataforma.",
        error: true,
      });
    }
    return response;
  }

  async function bootstrapAuthenticatedWorkspace(): Promise<void> {
    setIsBootstrappingWorkspace(true);
    await Promise.allSettled([
      loadRecentAnalyses(),
      loadOllamaModels(),
      loadOllamaStatus(),
      loadParserProfiles(),
    ]);
    setIsBootstrappingWorkspace(false);
  }

  async function loadOllamaModels(): Promise<void> {
    try {
      const response = await fetchProtected("/providers/ollama/models");
      if (!response.ok) {
        throw new Error("Falha ao consultar os modelos locais.");
      }
      const payload = (await response.json()) as OllamaModelsResponse;
      setOllamaModels(Array.isArray(payload.models) ? payload.models : []);
      setRecommendedLocalModel(typeof payload.recommended_model === "string" ? payload.recommended_model : "");
    } catch {
      setOllamaModels([]);
      setRecommendedLocalModel("");
    }
  }

  async function loadOllamaStatus(): Promise<void> {
    setOllamaStatusState((current) => ({
      loading: true,
      error: "",
      data: current.data,
    }));

    try {
      const response = await fetchProtected("/providers/ollama/status");
      if (!response.ok) {
        throw new Error("Falha ao consultar o status do Ollama.");
      }
      const payload = (await response.json()) as OllamaStatusResponse;
      setOllamaStatusState({
        loading: false,
        error: "",
        data: payload,
      });
    } catch (error) {
      setOllamaStatusState((current) => ({
        loading: false,
        error: toErrorMessage(error, "Não foi possível consultar o status do Ollama."),
        data: current.data,
      }));
    }
  }

  async function loadParserProfiles(): Promise<void> {
    try {
      const response = await fetchProtected("/parser/profiles");
      if (!response.ok) {
        throw new Error("Falha ao consultar os perfis do parser.");
      }
      const payload = (await response.json()) as ParserProfileDefinition[] | unknown;
      const profiles = Array.isArray(payload) ? (payload as ParserProfileDefinition[]) : [];
      setParserProfiles(profiles);
      if (profiles.some((profile) => profile.key === "auto")) {
        setFormState((current) => ({ ...current, parserProfile: "auto" }));
      }
    } catch {
      setParserProfiles([]);
    }
  }

  async function loadRecentAnalyses(): Promise<void> {
    setRecentAnalysesState((current) => ({
      loading: true,
      error: "",
      items: current.items,
    }));

    try {
      const response = await fetchProtected("/analyses?limit=8");
      if (!response.ok) {
        throw new Error("Falha ao consultar as análises salvas.");
      }
      const payload = (await response.json()) as StoredAnalysisListItem[] | unknown;
      setRecentAnalysesState({
        loading: false,
        error: "",
        items: Array.isArray(payload) ? (payload as StoredAnalysisListItem[]) : [],
      });
    } catch (error) {
      setRecentAnalysesState((current) => ({
        loading: false,
        error: toErrorMessage(error, "Não foi possível carregar as análises salvas."),
        items: current.items,
      }));
    }
  }

  function mergeFinancialAliasItem(
    current: FinancialAliasCatalogResponse | null,
    kind: FinancialAliasKind,
    item: FinancialAliasItem
  ): FinancialAliasCatalogResponse {
    const safeCurrent = current || { clients: [], contracts: [] };
    const bucketKey = kind === "client" ? "clients" : "contracts";
    const nextBucket = safeCurrent[bucketKey].some((entry) => entry.entity_id === item.entity_id)
      ? safeCurrent[bucketKey].map((entry) => (entry.entity_id === item.entity_id ? item : entry))
      : [...safeCurrent[bucketKey], item];
    nextBucket.sort((left, right) => left.canonical_name.localeCompare(right.canonical_name, "pt-BR"));
    return {
      clients: bucketKey === "clients" ? nextBucket : safeCurrent.clients,
      contracts: bucketKey === "contracts" ? nextBucket : safeCurrent.contracts,
    };
  }

  async function loadFinancialAliases(): Promise<void> {
    setFinancialAliasesState((current) => ({
      loading: true,
      error: "",
      data: current.data,
    }));

    try {
      const response = await fetchProtected("/financial-aliases?limit=80");
      if (!response.ok) {
        throw new Error(await extractError(response));
      }
      const payload = (await response.json()) as FinancialAliasCatalogResponse;
      setFinancialAliasesState({
        loading: false,
        error: "",
        data: payload,
      });
    } catch (error) {
      setFinancialAliasesState((current) => ({
        loading: false,
        error: toErrorMessage(error, "Não foi possível carregar os aliases financeiros."),
        data: current.data,
      }));
    }
  }

  function handleAliasDraftChange(kind: FinancialAliasKind, entityId: number, value: string): void {
    setAliasDrafts((current) => ({
      ...current,
      [`${kind}:${entityId}`]: value,
    }));
  }

  async function handleAddFinancialAlias(kind: FinancialAliasKind, entityId: number): Promise<void> {
    const draftKey = `${kind}:${entityId}`;
    const alias = String(aliasDrafts[draftKey] || "").trim();
    if (!alias) {
      setAliasFeedback({
        message: "Digite um alias antes de salvar.",
        error: true,
      });
      return;
    }

    setAliasBusyKey(draftKey);
    setAliasFeedback({ message: "", error: false });
    try {
      const response = await fetchProtected("/financial-aliases", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          kind,
          entity_id: entityId,
          alias,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }
      const payload = (await response.json()) as FinancialAliasItem;
      setFinancialAliasesState((current) => ({
        loading: false,
        error: "",
        data: mergeFinancialAliasItem(current.data, kind, payload),
      }));
      setAliasDrafts((current) => ({
        ...current,
        [draftKey]: "",
      }));
      setAliasFeedback({
        message: `Alias salvo para ${payload.canonical_name}.`,
        error: false,
      });
    } catch (error) {
      setAliasFeedback({
        message: toErrorMessage(error, "Não foi possível salvar o alias financeiro."),
        error: true,
      });
    } finally {
      setAliasBusyKey(null);
    }
  }

  async function handleRemoveFinancialAlias(kind: FinancialAliasKind, entityId: number, alias: string): Promise<void> {
    const draftKey = `${kind}:${entityId}`;
    setAliasBusyKey(draftKey);
    setAliasFeedback({ message: "", error: false });
    try {
      const response = await fetchProtected("/financial-aliases", {
        method: "DELETE",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          kind,
          entity_id: entityId,
          alias,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }
      const payload = (await response.json()) as FinancialAliasItem;
      setFinancialAliasesState((current) => ({
        loading: false,
        error: "",
        data: mergeFinancialAliasItem(current.data, kind, payload),
      }));
      setAliasFeedback({
        message: `Alias removido de ${payload.canonical_name}.`,
        error: false,
      });
    } catch (error) {
      setAliasFeedback({
        message: toErrorMessage(error, "Não foi possível remover o alias financeiro."),
        error: true,
      });
    } finally {
      setAliasBusyKey(null);
    }
  }

  async function detectParserProfile(file: File | null): Promise<void> {
    if (!file) {
      parserDetectionRequestIdRef.current += 1;
      setParserDetectionState({ loading: false, error: "", data: null });
      return;
    }

    const requestId = parserDetectionRequestIdRef.current + 1;
    parserDetectionRequestIdRef.current = requestId;
    setParserDetectionState((current) => ({
      loading: true,
      error: "",
      data: current.data,
    }));

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("requested_profile", "auto");

      const response = await fetchProtected("/parser/detect", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as ParserDetectionState["data"];
      if (parserDetectionRequestIdRef.current !== requestId) {
        return;
      }

      setParserDetectionState({
        loading: false,
        error: "",
        data: payload,
      });
    } catch (error) {
      if (parserDetectionRequestIdRef.current !== requestId) {
        return;
      }
      setParserDetectionState({
        loading: false,
        error: toErrorMessage(error, "Não foi possível identificar a estrutura do arquivo enviado."),
        data: null,
      });
    }
  }

  function applyFormValue<K extends keyof typeof INITIAL_FORM_STATE>(
    name: K,
    value: (typeof INITIAL_FORM_STATE)[K],
    options: { markStale?: boolean } = {}
  ): void {
    const shouldMarkStale = options.markStale ?? true;
    setFormState((current) => ({ ...current, [name]: value }) as typeof INITIAL_FORM_STATE);
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
      message: "Os parâmetros mudaram. Refaça a revisão antes de gerar o relatório final.",
      error: true,
    });
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    const nextFiles = Array.from(event.target.files || []);
    applyFormValue("files", nextFiles, { markStale: true });
    applyFormValue("file", nextFiles[0] || null, { markStale: false });
  }

  function handleTemplateChange(event: ChangeEvent<HTMLInputElement>): void {
    const nextFile = event.target.files?.[0] || null;
    applyFormValue("templateFile", nextFile, { markStale: false });
  }

  async function handleReviewRequest(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedWorkbook) {
      setStatus({ message: "Selecione um arquivo financeiro válido para iniciar a análise.", error: true });
      return;
    }

    setIsLoadingReview(true);
    const timer = startChannelTimer("status", "Lendo a planilha, executando o crawler e consolidando o contexto");

    try {
      const response = await fetchProtected("/analysis/review", {
        method: "POST",
        body: buildReviewFormData(formState),
      });

      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as AnalysisReviewResponse;
      startTransition(() => {
        setReviewData(payload);
        setReviewStale(false);
        setGenerationHistoryState({ loading: false, error: "", items: [] });
        setHighlightGenerationId(null);
        setActiveReviewTab("overview");
        setActiveWorkspaceTab("review");
      });
      await loadGenerationHistory(payload.analysis_id);
      void loadRecentAnalyses();
      setSavedAnalysisId(String(payload.analysis_id));
      timer.stop();
      setStatus({
        message: [
          `Análise #${payload.analysis_id} pronta`,
          payload.stats?.parse_duration_ms != null
            ? `Leitura: ${describeParseOrigin(payload.stats?.parse_cache_hit)} em ${formatDuration(payload.stats.parse_duration_ms)}`
            : `Leitura: ${describeParseOrigin(payload.stats?.parse_cache_hit)}`,
          payload.stats?.parse_cache_saved_ms != null
            ? `Economia pelo cache: ${formatDuration(payload.stats.parse_cache_saved_ms)}`
            : null,
          payload.stats?.scrape_duration_ms != null
            ? `Crawler: ${formatDuration(payload.stats.scrape_duration_ms)}`
            : `Tempo total: ${formatDuration(timer.elapsedMs())}`,
          "Revise os blocos abaixo e só depois gere o relatório final.",
        ]
          .filter(Boolean)
          .join(" | "),
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
        message: toErrorMessage(error, "Falha ao analisar o arquivo financeiro enviado."),
        error: true,
      });
    } finally {
      timer.stop();
      setIsLoadingReview(false);
    }
  }

  function hydrateFormFromStoredAnalysis(parsed: ChecklistParseResult, analysisId: number | string): void {
    setFormState((current) => ({
      ...current,
      file: null,
      files: [],
      parserProfile: parsed?.parser_options?.profile || current.parserProfile,
      allowedGroups: Array.isArray(parsed?.parser_options?.allowed_groups)
        ? parsed.parser_options.allowed_groups.join(",")
        : "",
      allowedStatus: Array.isArray(parsed?.parser_options?.allowed_status)
        ? parsed.parser_options.allowed_status.join(",")
        : "",
      checklistSheetName: formatStoredSheetSelection(parsed?.parser_options),
      periodoAnalise: parsed?.periodo_analise || "",
      numeroRelatorio: parsed?.numero_relatorio || "",
      solicitacao: parsed?.solicitacao || "",
      requesterArea: parsed?.promotoria || "",
      referencia: parsed?.referencia || "",
      cidadeEmissao: parsed?.cidade_emissao || "",
      dataEmissao: parsed?.data_emissao || "",
      periodoColeta: parsed?.periodo_coleta || "",
      relatorioContabilReferencia: parsed?.relatorio_contabil_referencia || "",
      equipeTecnica: parsed?.equipe_tecnica || "",
      orgao: parsed?.orgao || "",
      layoutProfile: inferLayoutProfile(parsed?.tipo_orgao),
    }));
    setSavedAnalysisId(String(analysisId));
  }

  async function handleLoadStoredAnalysis(analysisId: string | number = savedAnalysisId): Promise<boolean> {
    const normalizedId = String(analysisId || "").trim();
    if (!/^\d+$/.test(normalizedId)) {
      setStatus({ message: "Informe um ID numérico válido para abrir uma análise salva.", error: true });
      return false;
    }

    setIsLoadingStoredAnalysis(true);
    setStatus({
      message: `Recuperando a análise #${normalizedId} do histórico salvo.`,
      error: false,
    });

    try {
      const response = await fetchProtected(`/analysis/${normalizedId}/review`);
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as AnalysisReviewResponse;
      hydrateFormFromStoredAnalysis(payload.parsed, payload.analysis_id);
      startTransition(() => {
        setReviewData(payload);
        setReviewStale(false);
        setGenerationHistoryState({ loading: false, error: "", items: [] });
        setHighlightGenerationId(null);
        setActiveReviewTab("overview");
        setActiveWorkspaceTab("review");
      });
      await loadGenerationHistory(payload.analysis_id);
      setStatus({
        message: [
          `Análise #${payload.analysis_id} reaberta do histórico`,
          payload.stats?.parse_duration_ms != null
            ? `Leitura: ${describeParseOrigin(payload.stats?.parse_cache_hit)} em ${formatDuration(payload.stats.parse_duration_ms)}`
            : `Leitura: ${describeParseOrigin(payload.stats?.parse_cache_hit)}`,
          payload.stats?.parse_cache_saved_ms != null
            ? `Economia pelo cache: ${formatDuration(payload.stats.parse_cache_saved_ms)}`
            : null,
          `Itens: ${payload.stats?.extracted_item_count ?? 0}`,
          `Páginas: ${payload.stats?.scraped_page_count ?? 0}`,
          "Para alterar a extração, reenvie o arquivo. Para exportar, ajuste somente template e saída.",
        ]
          .filter(Boolean)
          .join(" | "),
        error: false,
      });
      window.setTimeout(() => {
        reviewPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 90);
      return true;
    } catch (error) {
      setStatus({
        message: toErrorMessage(error, "Não foi possível abrir a análise salva."),
        error: true,
      });
      return false;
    } finally {
      setIsLoadingStoredAnalysis(false);
    }
  }

  async function loadGenerationHistory(
    analysisId: number | string,
    highlightId: string | number | null = null
  ): Promise<void> {
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
      const response = await fetchProtected(`/analysis/${analysisId}/generations`);
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as GenerationTraceItem[];
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
        error: toErrorMessage(error, "Não foi possível carregar o histórico de geração."),
        items: [],
      });
    }
  }

  async function handleGenerateReport(): Promise<void> {
    if (!reviewData) {
      setStatus({ message: "Execute a revisão antes de gerar o relatório final.", error: true });
      return;
    }
    if (reviewStale) {
      setStatus({
        message: "Os campos mudaram depois da última revisão. Refaça a análise antes de gerar.",
        error: true,
      });
      return;
    }

    setIsGenerating(true);
    const timer = startChannelTimer("status", "Compondo o relatório e registrando a trilha da execução");

    try {
      const response = await fetchProtected(`/analysis/${reviewData.analysis_id}/report`, {
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
      void loadRecentAnalyses();
      timer.stop();
      setStatus({
        message: [
          `Relatório gerado: ${fileName}`,
          analysisId ? `Análise #${analysisId}` : null,
          provider ? `Provedor: ${humanizeProvider(provider)}` : null,
          model ? `Modelo: ${model}` : null,
          `Tempo de geração: ${formatDuration(durationMs)}`,
        ]
          .filter(Boolean)
          .join(" | "),
        error: false,
      });
    } catch (error) {
      timer.stop();
      setStatus({
        message: toErrorMessage(error, "Falha ao gerar o relatorio."),
        error: true,
      });
    } finally {
      timer.stop();
      setIsGenerating(false);
    }
  }

  async function handleScrape(event: FormEvent<HTMLFormElement>): Promise<void> {
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

      const response = await fetchProtected(`/scrape/links?${query.toString()}`);
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as ScrapePageResult;
      const nextScrapeTab: ActiveScrapeTab = Array.isArray(payload.links) && payload.links.length
        ? "links"
        : Array.isArray(payload.discovered_pages) && payload.discovered_pages.length
          ? "pages"
          : Array.isArray(payload.warnings) && payload.warnings.length
            ? "warnings"
            : "links";
      startTransition(() => {
        setScrapeResult(payload);
        setActiveScrapeTab(nextScrapeTab);
        setActiveWorkspaceTab("crawler");
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
        message: toErrorMessage(error, "Falha ao executar o crawler."),
        error: true,
      });
    } finally {
      timer.stop();
      setIsScraping(false);
    }
  }

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmittingAuth(true);
    setAuthFeedback({ message: "", error: false });

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          email: loginForm.email,
          password: loginForm.password,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as AuthSessionResponse;
      resetWorkspaceState();
      setSessionState({
        loading: false,
        user: payload.user || null,
        session: payload.session || null,
        error: "",
      });
      setAuthFeedback({ message: "", error: false });
      setStatus({
        message: "Sessão iniciada. Envie um arquivo e execute a revisão para abrir o fluxo completo.",
        error: false,
      });
    } catch (error) {
      setAuthFeedback({
        message: toErrorMessage(error, "Não foi possível entrar na plataforma."),
        error: true,
      });
    } finally {
      setIsSubmittingAuth(false);
    }
  }

  async function handleRegisterSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmittingAuth(true);
    setAuthFeedback({ message: "", error: false });

    try {
      const response = await fetch("/auth/register", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          full_name: registerForm.fullName,
          email: registerForm.email,
          password: registerForm.password,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as AuthSessionResponse;
      resetWorkspaceState();
      setSessionState({
        loading: false,
        user: payload.user || null,
        session: payload.session || null,
        error: "",
      });
      setAuthFeedback({ message: "", error: false });
      setStatus({
        message: "Conta criada com sucesso. O workspace privado já está liberado para a primeira análise.",
        error: false,
      });
    } catch (error) {
      setAuthFeedback({
        message: toErrorMessage(error, "Não foi possível criar a conta."),
        error: true,
      });
    } finally {
      setIsSubmittingAuth(false);
    }
  }

  function handleAuthModeChange(mode: AuthMode): void {
    setAuthMode(mode);
    setAuthFeedback({ message: "", error: false });

    if (mode === "forgot") {
      setForgotPasswordForm((current) => ({
        email: current.email || loginForm.email || registerForm.email,
      }));
    }

    if (mode !== "reset") {
      setResetPasswordForm((current) => ({
        token: mode === "login" ? "" : current.token,
        newPassword: "",
        confirmPassword: "",
      }));
    }
  }

  async function handleForgotPasswordSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmittingAuth(true);
    setAuthFeedback({ message: "", error: false });

    try {
      const response = await fetch("/auth/password/forgot", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          email: forgotPasswordForm.email,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as AuthPasswordForgotResponse;
      if (payload.reset_token) {
        setResetPasswordForm({
          token: payload.reset_token,
          newPassword: "",
          confirmPassword: "",
        });
        setAuthMode("reset");
        setAuthFeedback({
          message: payload.expires_at
            ? `Fluxo de teste preparado. O token foi preenchido automaticamente e expira em ${payload.expires_at}.`
            : "Fluxo de teste preparado. O token foi preenchido automaticamente para a redefinição.",
          error: false,
        });
      } else {
        setAuthFeedback({
          message:
            payload.message ||
            "Se o e-mail existir, o fluxo de redefinição foi preparado. Em produção, isso seguiria por e-mail.",
          error: false,
        });
      }
    } catch (error) {
      setAuthFeedback({
        message: toErrorMessage(error, "Não foi possível preparar a redefinição de senha."),
        error: true,
      });
    } finally {
      setIsSubmittingAuth(false);
    }
  }

  async function handleResetPasswordSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmittingAuth(true);
    setAuthFeedback({ message: "", error: false });

    if (resetPasswordForm.newPassword !== resetPasswordForm.confirmPassword) {
      setAuthFeedback({
        message: "A confirmação da nova senha precisa ser igual ao novo valor.",
        error: true,
      });
      setIsSubmittingAuth(false);
      return;
    }

    try {
      const response = await fetch("/auth/password/reset", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          token: resetPasswordForm.token,
          new_password: resetPasswordForm.newPassword,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      setResetPasswordForm({
        token: "",
        newPassword: "",
        confirmPassword: "",
      });
      setForgotPasswordForm({
        email: "",
      });
      setLoginForm((current) => ({
        ...current,
        email: forgotPasswordForm.email || current.email,
        password: "",
      }));
      setAuthMode("login");
      setAuthFeedback({
        message: "Senha redefinida com sucesso. Faça login com o novo valor.",
        error: false,
      });
    } catch (error) {
      setAuthFeedback({
        message: toErrorMessage(error, "Não foi possível redefinir a senha."),
        error: true,
      });
    } finally {
      setIsSubmittingAuth(false);
    }
  }

  async function handleLogout(): Promise<void> {
    setIsLoggingOut(true);
    try {
      await fetch("/auth/logout", { method: "POST" });
    } finally {
      resetWorkspaceState();
      setSessionState({
        loading: false,
        user: null,
        session: null,
        error: "",
      });
      setAuthMode("login");
      setAuthFeedback({
        message: "Sessão encerrada. Entre novamente para acessar a área privada.",
        error: false,
      });
      setIsLoggingOut(false);
    }
  }

  async function handleAccountProfileSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSavingAccountProfile(true);
    setAccountProfileFeedback({ message: "", error: false });

    try {
      const response = await fetchProtected("/auth/profile", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          full_name: accountProfileForm.fullName,
          email: accountProfileForm.email,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      const payload = (await response.json()) as AuthSessionResponse;
      setSessionState((current) => ({
        ...current,
        user: payload.user || current.user,
        session: payload.session || current.session,
      }));
      setAccountProfileFeedback({
        message: "Perfil atualizado com sucesso.",
        error: false,
      });
    } catch (error) {
      setAccountProfileFeedback({
        message: toErrorMessage(error, "Não foi possível atualizar o perfil."),
        error: true,
      });
    } finally {
      setIsSavingAccountProfile(false);
    }
  }

  async function handleAccountPasswordSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setAccountPasswordFeedback({ message: "", error: false });

    if (accountPasswordForm.newPassword !== accountPasswordForm.confirmPassword) {
      setAccountPasswordFeedback({
        message: "A confirmação da nova senha precisa ser igual ao novo valor.",
        error: true,
      });
      return;
    }

    setIsSavingAccountPassword(true);

    try {
      const response = await fetchProtected("/auth/password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          current_password: accountPasswordForm.currentPassword,
          new_password: accountPasswordForm.newPassword,
        }),
      });
      if (!response.ok) {
        throw new Error(await extractError(response));
      }

      setAccountPasswordForm({
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      });
      setAccountPasswordFeedback({
        message: "Senha atualizada com sucesso.",
        error: false,
      });
    } catch (error) {
      setAccountPasswordFeedback({
        message: toErrorMessage(error, "Não foi possível atualizar a senha."),
        error: true,
      });
    } finally {
      setIsSavingAccountPassword(false);
    }
  }

  const studioMetrics: WorkspaceMetric[] = deferredReview
    ? [
        {
          label: "Itens elegíveis",
          value: String(deferredReview.stats?.extracted_item_count ?? 0),
          icon: FileSearch,
        },
        {
          label: "Páginas rastreadas",
          value: String(deferredReview.stats?.scraped_page_count ?? 0),
          icon: Globe2,
        },
        {
          label: "Tempo do crawler",
          value: formatDuration(deferredReview.stats?.scrape_duration_ms),
          icon: TimerReset,
        },
        {
          label: "Tempo de leitura",
          value: formatDuration(deferredReview.stats?.parse_duration_ms),
          icon: FileSearch,
        },
        ...(deferredReview.stats?.parse_cache_saved_ms != null
          ? [
              {
                label: "Economia do cache",
                value: formatDuration(deferredReview.stats?.parse_cache_saved_ms),
                icon: TimerReset,
              },
            ]
          : []),
        {
          label: "Execuções registradas",
          value: String(generationHistoryState.items.length),
          icon: History,
        },
      ]
    : [
        { label: "Parser", value: selectedParserProfile?.label || "Estendido", icon: Filter },
        { label: "Modelos locais", value: String(ollamaModels.length), icon: Bot },
        { label: "Perfis do parser", value: String(parserProfiles.length), icon: Waypoints },
        { label: "Estado", value: reviewReady ? "Pronto" : "Aguardando revisão", icon: ShieldCheck },
      ];

  const workspaceTabs: TabDescriptor[] = [
    { key: "composer", label: "Configuração", icon: Filter },
    {
      key: "review",
      label: "Revisão",
      icon: FileSearch,
      count: deferredReview ? deferredReview.stats?.extracted_item_count ?? 0 : undefined,
    },
    {
      key: "crawler",
      label: "Crawler",
      icon: Globe2,
      count: scrapeResult?.discovered_pages?.length ?? scrapeResult?.links?.length ?? undefined,
    },
  ];

  async function handleStoredAnalysisModalSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const loaded = await handleLoadStoredAnalysis();
    if (loaded) {
      setActiveUtilityModal(null);
    }
  }

  async function handleStoredAnalysisModalClick(analysisId: number): Promise<void> {
    const loaded = await handleLoadStoredAnalysis(analysisId);
    if (loaded) {
      setActiveUtilityModal(null);
    }
  }

  function handleRefreshLocalAi(): void {
    void loadOllamaModels();
    void loadOllamaStatus();
  }

  function handleRefreshFinancialAliases(): void {
    void loadFinancialAliases();
  }

  if (sessionState.loading) {
    return (
      <div className="site-shell site-shell-loading">
        <div className="ambient ambient-a" />
        <div className="ambient ambient-b" />
        <div className="ambient ambient-c" />
        <div className="glass-panel site-loading-card">
          <span className="eyebrow">Draux Inc.</span>
          <h1>Preparando a plataforma privada</h1>
          <p className="hero-lead">Estamos validando sua sessão antes de liberar o acesso ao workspace.</p>
        </div>
      </div>
    );
  }

  if (!sessionState.user) {
    return (
      <MarketingAuthShell
        authMode={authMode}
        onAuthModeChange={handleAuthModeChange}
        loginForm={loginForm}
        registerForm={registerForm}
        forgotPasswordForm={forgotPasswordForm}
        resetPasswordForm={resetPasswordForm}
        onLoginFieldChange={(field: keyof LoginForm, value: string) =>
          setLoginForm((current) => ({ ...current, [field]: value }))
        }
        onRegisterFieldChange={(field: keyof RegisterForm, value: string) =>
          setRegisterForm((current) => ({ ...current, [field]: value }))
        }
        onForgotPasswordFieldChange={(field: keyof ForgotPasswordForm, value: string) =>
          setForgotPasswordForm((current) => ({ ...current, [field]: value }))
        }
        onResetPasswordFieldChange={(field: keyof ResetPasswordForm, value: string) =>
          setResetPasswordForm((current) => ({ ...current, [field]: value }))
        }
        onLoginSubmit={handleLoginSubmit}
        onRegisterSubmit={handleRegisterSubmit}
        onForgotPasswordSubmit={handleForgotPasswordSubmit}
        onResetPasswordSubmit={handleResetPasswordSubmit}
        authFeedback={authFeedback}
        sessionError={sessionState.error}
        authLoading={isSubmittingAuth}
      />
    );
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <div className="ambient ambient-c" />

      <header className="glass-panel product-topbar">
        <div className="product-topbar-copy">
          <span className="eyebrow">Área autenticada</span>
          <h2>Draux Inc. Workspace</h2>
          <p className="panel-copy">
            {isBootstrappingWorkspace
              ? "Carregando modelos, perfis e análises da sua conta."
              : "Sua conta está pronta para revisar e gerar entregas com mais clareza."}
          </p>
        </div>

        <div className="product-topbar-actions">
          <div className="product-account-card">
            <span className="product-account-avatar">{userInitials || "DI"}</span>
            <div className="product-account-copy">
              <strong>{sessionState.user.full_name}</strong>
              <span>{sessionState.user.email}</span>
            </div>
          </div>
          <button
            className="action-button action-button-ghost"
            type="button"
            onClick={() => setActiveUtilityModal("account")}
          >
            Conta
          </button>
          <button
            className="action-button action-button-ghost"
            type="button"
            onClick={handleLogout}
            disabled={isLoggingOut}
          >
            {isLoggingOut ? "Saindo..." : "Sair"}
          </button>
        </div>
      </header>

      <WorkspaceHero primaryStatusTone={primaryStatusTone} reviewReady={reviewReady} studioMetrics={studioMetrics} />

      <main id="workspace" className="workspace-shell workspace-shell-focused">
        <section className="workspace-main workspace-main-full">
          <WorkspaceHub
            activeTab={activeWorkspaceTab}
            onTabChange={(tab) => setActiveWorkspaceTab(tab as ActiveWorkspaceTab)}
            tabs={workspaceTabs}
            primaryStatusTone={primaryStatusTone}
            reviewReady={reviewReady}
            reviewStale={reviewStale}
            reviewData={reviewData}
            recentAnalysesCount={recentAnalysesState.items.length}
            localAiAvailable={Boolean(ollamaStatusState.data?.available)}
            onOpenModal={(modal) => setActiveUtilityModal(modal)}
          />

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={activeWorkspaceTab}
              className="workspace-stage"
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              <Suspense fallback={<WorkspaceStageLoader tabKey={activeWorkspaceTab} />}>
                {activeWorkspaceTab === "composer" ? (
                  <ComposerPanel
                    formState={formState}
                    selectedParserProfile={selectedParserProfile}
                    activeParserProfile={activeParserProfile}
                    parserProfiles={parserProfiles}
                    parserDetectionState={parserDetectionState}
                    ollamaModels={ollamaModels}
                    recommendedLocalModel={recommendedLocalModel}
                    applyFormValue={applyFormValue}
                    handleFileChange={handleFileChange}
                    handleTemplateChange={handleTemplateChange}
                    handleReviewRequest={handleReviewRequest}
                    primaryStatusTone={primaryStatusTone}
                    status={status}
                    isLoadingReview={isLoadingReview}
                    reviewReady={reviewReady}
                    isGenerating={isGenerating}
                    handleGenerateReport={handleGenerateReport}
                  />
                ) : null}

                {activeWorkspaceTab === "review" ? (
                  deferredReview ? (
                    <ReviewPanel
                      review={deferredReview}
                      panelRef={reviewPanelRef}
                      activeTab={activeReviewTab}
                      onTabChange={(tab) => setActiveReviewTab(tab as ActiveReviewTab)}
                      generationHistoryState={generationHistoryState}
                      highlightGenerationId={highlightGenerationId}
                      formState={formState}
                      recommendedLocalModel={recommendedLocalModel}
                    />
                  ) : (
                    <section className="glass-panel workspace-placeholder">
                      <span className="eyebrow">Revisão</span>
                      <h2>Execute uma análise antes de abrir a revisão detalhada</h2>
                      <p className="body-copy">
                        A aba de revisão concentra alertas, camadas, itens, crawler, prompt e histórico.
                        Primeiro configure a entrada e rode a revisão para liberar esse painel.
                      </p>
                      <div className="action-buttons">
                        <button className="action-button" type="button" onClick={() => setActiveWorkspaceTab("composer")}>
                          Ir para configuração
                        </button>
                        <button
                          className="action-button action-button-ghost"
                          type="button"
                          onClick={() => setActiveUtilityModal("analyses")}
                        >
                          Abrir análises salvas
                        </button>
                      </div>
                    </section>
                  )
                ) : null}

                {activeWorkspaceTab === "crawler" ? (
                  <CrawlerPanel
                    formState={formState}
                    applyFormValue={applyFormValue}
                    handleScrape={handleScrape}
                    isScraping={isScraping}
                    scrapeStatusTone={scrapeStatusTone}
                    scrapeStatus={scrapeStatus}
                    scrapeResult={scrapeResult}
                    scrapeResultRef={scrapeResultRef}
                    activeScrapeTab={activeScrapeTab}
                    onScrapeTabChange={(tab: ActiveScrapeTab) => setActiveScrapeTab(tab)}
                  />
                ) : null}
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </section>

        <WorkspaceUtilityModal
          activeModal={activeUtilityModal}
          onClose={() => setActiveUtilityModal(null)}
          primaryStatusTone={primaryStatusTone}
          status={status}
          recentAnalysesState={recentAnalysesState}
          reviewData={reviewData}
          isLoadingStoredAnalysis={isLoadingStoredAnalysis}
          savedAnalysisId={savedAnalysisId}
          setSavedAnalysisId={setSavedAnalysisId}
          selectedParserProfile={selectedParserProfile}
          onStoredAnalysisSubmit={handleStoredAnalysisModalSubmit}
          onStoredAnalysisClick={handleStoredAnalysisModalClick}
          ollamaStatusState={ollamaStatusState}
          recommendedLocalModel={recommendedLocalModel}
          onRefreshLocalAi={handleRefreshLocalAi}
          financialAliasesState={financialAliasesState}
          aliasDrafts={aliasDrafts}
          aliasBusyKey={aliasBusyKey}
          aliasFeedback={aliasFeedback}
          onAliasDraftChange={handleAliasDraftChange}
          onAddFinancialAlias={handleAddFinancialAlias}
          onRemoveFinancialAlias={handleRemoveFinancialAlias}
          onRefreshFinancialAliases={handleRefreshFinancialAliases}
          accountProfileForm={accountProfileForm}
          sessionInfo={sessionState.session}
          onAccountProfileFieldChange={(field, value) =>
            setAccountProfileForm((current) => ({ ...current, [field]: value }))
          }
          onAccountProfileSubmit={handleAccountProfileSubmit}
          isSavingAccountProfile={isSavingAccountProfile}
          accountProfileFeedback={accountProfileFeedback}
          accountPasswordForm={accountPasswordForm}
          onAccountPasswordFieldChange={(field, value) =>
            setAccountPasswordForm((current) => ({ ...current, [field]: value }))
          }
          onAccountPasswordSubmit={handleAccountPasswordSubmit}
          isSavingAccountPassword={isSavingAccountPassword}
          accountPasswordFeedback={accountPasswordFeedback}
        />
      </main>
    </div>
  );
}
