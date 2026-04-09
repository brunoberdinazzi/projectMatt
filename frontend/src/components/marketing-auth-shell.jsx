import { motion } from "framer-motion";
import {
  ArrowRight,
  BadgeCheck,
  Bot,
  ChartNoAxesCombined,
  FileSearch,
  Globe2,
  LockKeyhole,
  ScanSearch,
  Sparkles,
  Workflow,
} from "lucide-react";

import { StatusBlock, Tag, TextField } from "./ui";

const PANEL_VARIANTS = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.48, ease: [0.22, 1, 0.36, 1] },
  },
};

const STAGGER_VARIANTS = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.07,
      delayChildren: 0.04,
    },
  },
};

const PLATFORM_HIGHLIGHTS = [
  {
    icon: Workflow,
    title: "Leitura estruturada",
    copy: "Consolide arquivos, contexto e evidências em uma única leitura.",
  },
  {
    icon: ScanSearch,
    title: "Crawler guiado por evidências",
    copy: "Rastreie links e páginas relevantes antes da composição final.",
  },
  {
    icon: Bot,
    title: "Geração auditável",
    copy: "Veja modelo, fallback e duração em cada entrega.",
  },
];

const JOURNEY_STEPS = [
  {
    icon: LockKeyhole,
    title: "Conta privada",
    copy: "Cada operador trabalha em uma área autenticada com histórico próprio.",
  },
  {
    icon: FileSearch,
    title: "Revisão estruturada",
    copy: "O workspace separa configuração, revisão e crawler em etapas claras.",
  },
  {
    icon: ChartNoAxesCombined,
    title: "Entrega pronta para apresentação",
    copy: "O produto organiza contexto, narrativa e saída final em um fluxo demonstrável.",
  },
];

const ACCESS_BENEFITS = [
  "Acesso privado",
  "Histórico por operador",
  "Crawler e IA no mesmo fluxo",
];

export function MarketingAuthShell({
  authMode,
  onAuthModeChange,
  loginForm,
  registerForm,
  forgotPasswordForm,
  resetPasswordForm,
  onLoginFieldChange,
  onRegisterFieldChange,
  onForgotPasswordFieldChange,
  onResetPasswordFieldChange,
  onLoginSubmit,
  onRegisterSubmit,
  onForgotPasswordSubmit,
  onResetPasswordSubmit,
  authFeedback,
  sessionError,
  authLoading,
}) {
  const statusMessage = authFeedback.message || sessionError;
  const statusTone = authFeedback.error || sessionError ? "error" : "ready";

  return (
    <div className="site-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />
      <div className="ambient ambient-c" />

      <motion.header className="glass-panel site-nav" initial="hidden" animate="visible" variants={PANEL_VARIANTS}>
        <div className="site-brand">
          <span className="eyebrow">Draux Inc.</span>
          <strong>Relatórios técnicos com contexto, revisão e auditoria em uma única plataforma.</strong>
        </div>
        <div className="site-nav-actions">
          <a className="secondary-link" href="#site-journey">
            Ver fluxo
          </a>
          <a className="primary-link" href="#site-access">
            Entrar na plataforma
            <ArrowRight size={18} />
          </a>
        </div>
      </motion.header>

      <main className="site-main">
        <motion.section
          className="site-hero-shell"
          initial="hidden"
          animate="visible"
          variants={STAGGER_VARIANTS}
        >
          <motion.article className="glass-panel site-hero-panel" variants={PANEL_VARIANTS}>
            <div className="site-hero-copy">
              <span className="eyebrow">Plataforma privada</span>
              <h1>Draux Inc. transforma análise técnica em operação assistida por contexto.</h1>
              <p className="hero-lead">
                A entrada pública apresenta o produto e libera o workspace privado apenas depois da autenticação.
                O resultado é uma experiência mais clara para demonstração, onboarding e uso recorrente.
              </p>

              <div className="site-proof-strip">
                <Tag icon={BadgeCheck}>Conta e sessão próprias</Tag>
                <Tag icon={Globe2}>Crawler e contexto web</Tag>
                <Tag icon={Sparkles}>IA local e remota</Tag>
              </div>

              <div className="site-metric-strip">
                <article className="site-metric-card">
                  <strong>01</strong>
                  <span>Acesso autenticado.</span>
                </article>
                <article className="site-metric-card">
                  <strong>02</strong>
                  <span>Workspace com revisão e crawler.</span>
                </article>
                <article className="site-metric-card">
                  <strong>03</strong>
                  <span>Entrega final auditável.</span>
                </article>
              </div>
            </div>

            <div className="site-proof-grid">
              {PLATFORM_HIGHLIGHTS.map(({ icon: Icon, title, copy }) => (
                <article key={title} className="site-proof-card">
                  <span className="icon-badge icon-badge-soft">
                    <Icon size={18} />
                  </span>
                  <h3>{title}</h3>
                  <p>{copy}</p>
                </article>
              ))}
            </div>
          </motion.article>

          <motion.aside id="site-access" className="glass-panel site-auth-card" variants={PANEL_VARIANTS}>
            <div className="site-auth-head">
              <span className="eyebrow eyebrow-soft">Acesso ao produto</span>
              <h2>Entre na área privada</h2>
              <p className="panel-copy">
                Entre com sua conta ou crie um novo acesso para liberar o workspace completo.
              </p>
            </div>

            <div className="site-access-benefits" aria-label="Benefícios do acesso">
              {ACCESS_BENEFITS.map((item) => (
                <span key={item} className="site-access-benefit">
                  {item}
                </span>
              ))}
            </div>

            <div className="site-auth-tabs" role="tablist" aria-label="Escolha o modo de autenticação">
              <button
                className={`site-auth-tab ${authMode === "login" || authMode === "forgot" || authMode === "reset" ? "site-auth-tab-active" : ""}`}
                type="button"
                onClick={() => onAuthModeChange("login")}
              >
                Entrar
              </button>
              <button
                className={`site-auth-tab ${authMode === "register" ? "site-auth-tab-active" : ""}`}
                type="button"
                onClick={() => onAuthModeChange("register")}
              >
                Criar conta
              </button>
            </div>

            {statusMessage ? <StatusBlock tone={statusTone} message={statusMessage} compact /> : null}

            {authMode === "login" ? (
              <form className="site-auth-form" onSubmit={onLoginSubmit}>
                <TextField
                  label="E-mail corporativo"
                  type="email"
                  autoComplete="email"
                  placeholder="voce@empresa.com"
                  value={loginForm.email}
                  onChange={(event) => onLoginFieldChange("email", event.target.value)}
                />
                <TextField
                  label="Senha"
                  type="password"
                  autoComplete="current-password"
                  placeholder="Digite sua senha"
                  value={loginForm.password}
                  onChange={(event) => onLoginFieldChange("password", event.target.value)}
                />
                <button className="action-button site-auth-submit" type="submit" disabled={authLoading}>
                  {authLoading ? "Entrando..." : "Entrar na plataforma"}
                </button>
                <button
                  className="text-action-button"
                  type="button"
                  onClick={() => onAuthModeChange("forgot")}
                  disabled={authLoading}
                >
                  Esqueci minha senha
                </button>
              </form>
            ) : authMode === "forgot" ? (
              <form className="site-auth-form" onSubmit={onForgotPasswordSubmit}>
                <TextField
                  label="E-mail da conta"
                  type="email"
                  autoComplete="email"
                  placeholder="voce@empresa.com"
                  value={forgotPasswordForm.email}
                  onChange={(event) => onForgotPasswordFieldChange("email", event.target.value)}
                />
                <button className="action-button site-auth-submit" type="submit" disabled={authLoading}>
                  {authLoading ? "Preparando..." : "Preparar redefinição"}
                </button>
                <p className="site-auth-support-copy">
                  Em ambiente local, o token de teste pode voltar na resposta e preencher a próxima etapa
                  automaticamente.
                </p>
                <button
                  className="text-action-button"
                  type="button"
                  onClick={() => onAuthModeChange("login")}
                  disabled={authLoading}
                >
                  Voltar para o login
                </button>
              </form>
            ) : authMode === "reset" ? (
              <form className="site-auth-form" onSubmit={onResetPasswordSubmit}>
                <TextField
                  label="Token de redefinição"
                  autoComplete="one-time-code"
                  placeholder="Cole o token recebido"
                  value={resetPasswordForm.token}
                  onChange={(event) => onResetPasswordFieldChange("token", event.target.value)}
                />
                <TextField
                  label="Nova senha"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Mínimo de 8 caracteres"
                  value={resetPasswordForm.newPassword}
                  onChange={(event) => onResetPasswordFieldChange("newPassword", event.target.value)}
                />
                <TextField
                  label="Confirmar nova senha"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Repita a nova senha"
                  value={resetPasswordForm.confirmPassword}
                  onChange={(event) => onResetPasswordFieldChange("confirmPassword", event.target.value)}
                />
                <button className="action-button site-auth-submit" type="submit" disabled={authLoading}>
                  {authLoading ? "Redefinindo..." : "Redefinir senha"}
                </button>
                <p className="site-auth-support-copy">
                  Use o token recebido no fluxo de teste local ou no e-mail de redefinição quando esse envio estiver
                  conectado.
                </p>
                <button
                  className="text-action-button"
                  type="button"
                  onClick={() => onAuthModeChange("login")}
                  disabled={authLoading}
                >
                  Voltar para o login
                </button>
              </form>
            ) : (
              <form className="site-auth-form" onSubmit={onRegisterSubmit}>
                <TextField
                  label="Nome completo"
                  autoComplete="name"
                  placeholder="Ex.: Ana Rodrigues"
                  value={registerForm.fullName}
                  onChange={(event) => onRegisterFieldChange("fullName", event.target.value)}
                />
                <TextField
                  label="E-mail corporativo"
                  type="email"
                  autoComplete="email"
                  placeholder="voce@empresa.com"
                  value={registerForm.email}
                  onChange={(event) => onRegisterFieldChange("email", event.target.value)}
                />
                <TextField
                  label="Senha"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Minimo de 8 caracteres"
                  value={registerForm.password}
                  onChange={(event) => onRegisterFieldChange("password", event.target.value)}
                />
                <button className="action-button site-auth-submit" type="submit" disabled={authLoading}>
                  {authLoading ? "Criando..." : "Criar conta e acessar"}
                </button>
              </form>
            )}

            <p className="site-auth-note">
              Sessão com cookie seguro no backend. As novas análises ficam associadas ao usuário autenticado.
            </p>
          </motion.aside>
        </motion.section>

        <motion.section
          id="site-journey"
          className="glass-panel site-journey-panel"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.25 }}
          variants={PANEL_VARIANTS}
        >
          <div className="panel-header">
            <div>
              <span className="eyebrow">Jornada do produto</span>
              <h2>Uma entrada comercial na frente, um workspace operacional por trás</h2>
            </div>
            <p className="panel-copy">
              A landing qualifica a proposta e o acesso. Depois do login, o operador entra em um ambiente
              focado na execução do fluxo completo, sem poluição desnecessária.
            </p>
          </div>

          <div className="site-journey-grid">
            {JOURNEY_STEPS.map(({ icon: Icon, title, copy }) => (
              <article key={title} className="site-step-card">
                <span className="icon-badge">
                  <Icon size={18} />
                </span>
                <h3>{title}</h3>
                <p>{copy}</p>
              </article>
            ))}
          </div>
        </motion.section>
      </main>
    </div>
  );
}
