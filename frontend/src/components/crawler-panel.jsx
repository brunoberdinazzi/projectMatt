import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowUpRight,
  Globe2,
  Link2,
  ScanSearch,
  TimerReset,
  Waypoints,
} from "lucide-react";

import {
  formatDuration,
  humanizeCategory,
  humanizeDestination,
} from "../lib/app-utils";
import {
  EmptyBlock,
  GuideCard,
  StatusBlock,
  StatusPill,
  TabStrip,
  TextField,
} from "./ui";

const PANEL_VARIANTS = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
};

const TAB_VARIANTS = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 12 },
  transition: { duration: 0.24, ease: [0.22, 1, 0.36, 1] },
};

export function CrawlerPanel({
  formState,
  applyFormValue,
  handleScrape,
  isScraping,
  scrapeStatusTone,
  scrapeStatus,
  scrapeResult,
  scrapeResultRef,
  activeScrapeTab,
  onScrapeTabChange,
}) {
  const scrapeWarningCount = scrapeResult?.warnings?.length ?? 0;
  const scrapeLinkCount = scrapeResult?.links?.length ?? 0;
  const scrapePageCount = scrapeResult?.discovered_pages?.length ?? 0;

  const scrapeTabs = [
    { key: "links", label: "Links", icon: Link2, count: scrapeLinkCount },
    { key: "pages", label: "Páginas", icon: Globe2, count: scrapePageCount },
    { key: "warnings", label: "Alertas", icon: TimerReset, count: scrapeWarningCount },
  ];

  return (
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
          <h2>Teste uma origem antes de acoplá-la ao fluxo principal</h2>
        </div>
        <p className="panel-copy">
          Use este módulo para entender como o crawler classifica links, navega páginas
          relacionadas e mede o tempo de processamento fora da revisão completa.
        </p>
      </div>

      <div className="workflow-grid workflow-grid-tight">
        <GuideCard
          icon={Link2}
          title="Máximo de links"
          copy="Limita quantos links da origem entram no ranking retornado."
        />
        <GuideCard
          icon={Waypoints}
          title="Profundidade"
          copy="Controla quantos níveis o crawler percorre além da origem."
        />
        <GuideCard
          icon={Globe2}
          title="Páginas descobertas"
          copy="Define quantas páginas adicionais podem ser abertas."
        />
        <GuideCard
          icon={TimerReset}
          title="Tempo do processamento"
          copy="Expõe a duração do crawler para facilitar comparação entre parâmetros."
        />
      </div>

      <form className="composer-form" onSubmit={handleScrape}>
        <div className="field-grid">
          <TextField
            label="URL da página"
            type="url"
            placeholder="Ex.: https://example.com/"
            value={formState.scrapeUrl || ""}
            onChange={(event) => applyFormValue("scrapeUrl", event.target.value, { markStale: false })}
            required
          />
          <TextField
            label="Máximo de links"
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
            label="Máximo de páginas descobertas"
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
                  <h3>{scrapeResult.page_title || "Página inicial analisada"}</h3>
                  <p className="meta-line">
                    URL final: {scrapeResult.final_url}
                    {scrapeResult.processing_time_ms != null
                      ? ` | Tempo: ${formatDuration(scrapeResult.processing_time_ms)}`
                      : ""}
                    {Array.isArray(scrapeResult.discovered_pages) && scrapeResult.discovered_pages.length
                      ? ` | ${scrapeResult.discovered_pages.length} página(s) descoberta(s)`
                      : ""}
                  </p>
                </div>
                <StatusPill tone="ready" icon={ScanSearch}>
                  Crawler concluído
                </StatusPill>
              </div>
              <p className="body-copy">{scrapeResult.summary}</p>
            </article>

            <div className="panel-navigator panel-navigator-compact">
              <div>
                <span className="eyebrow eyebrow-soft">Saída organizada</span>
                <p className="navigator-copy">
                  Alterne entre links, páginas e alertas para inspecionar o crawl com menos ruído visual.
                </p>
              </div>
              <TabStrip tabs={scrapeTabs} activeKey={activeScrapeTab} onChange={onScrapeTabChange} />
            </div>

            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={activeScrapeTab}
                className="tab-panel"
                initial={TAB_VARIANTS.initial}
                animate={TAB_VARIANTS.animate}
                exit={TAB_VARIANTS.exit}
                transition={TAB_VARIANTS.transition}
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
                    <EmptyBlock message="Nenhum alerta foi registrado para esta execução do crawler." />
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
                            {link.section ? `Seção: ${link.section} | ` : ""}
                            {link.is_internal ? "Link interno" : "Link externo"}
                            {typeof link.score === "number" ? ` | Pontuação: ${link.score}` : ""}
                          </p>
                          {link.context ? <p className="body-copy">{link.context}</p> : null}
                          {link.evidence_summary ? <p className="body-copy strong-copy">{link.evidence_summary}</p> : null}
                        </article>
                      ))}
                    </div>
                  ) : (
                    <EmptyBlock message="Nenhum link priorizado foi retornado para os parâmetros usados." />
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
                              <p className="meta-line">Página descoberta</p>
                            </div>
                            <StatusPill tone="neutral" icon={Globe2}>
                              Profundidade {page.discovery_depth ?? 0}
                            </StatusPill>
                          </div>
                          <p className="meta-line">
                            {typeof page.page_score === "number" && page.page_score > 0
                              ? `Pontuação: ${page.page_score}`
                              : "Pontuação não informada"}
                            {page.discovered_from_label ? ` | Via: ${page.discovered_from_label}` : ""}
                          </p>
                          <p className="body-copy">{page.summary}</p>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <EmptyBlock message="Nenhuma página adicional foi descoberta com a profundidade atual." />
                  )
                ) : null}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}
