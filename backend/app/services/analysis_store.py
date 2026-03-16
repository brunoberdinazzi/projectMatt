from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from ..models import (
    ChecklistDetail,
    ChecklistItem,
    ChecklistParseResult,
    GenerationTrace,
    ParserOptions,
    ScrapedLink,
    ScrapedPageRecord,
    WorkbookContextLayer,
)


class AnalysisStore:
    def __init__(self, database_path: Optional[Path] = None) -> None:
        base_dir = Path(__file__).resolve().parents[3]
        data_dir = base_dir / "backend" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path or (data_dir / "matt.db")
        self._initialize()

    def create_analysis(
        self,
        parsed: ChecklistParseResult,
        source_filename: Optional[str] = None,
        generation_mode: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analyses (
                    source_filename,
                    orgao,
                    tipo_orgao,
                    periodo_analise,
                    sat_numero,
                    site_url,
                    portal_url,
                    esic_url,
                    numero_relatorio,
                    promotoria,
                    referencia,
                    solicitacao,
                    cidade_emissao,
                    data_emissao,
                    periodo_coleta,
                    equipe_tecnica,
                    relatorio_contabil_referencia,
                    fontes_disponiveis_json,
                    grupos_permitidos_json,
                    parser_options_json,
                    context_layers_json,
                    generation_mode,
                    output_format,
                    database_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_filename,
                    parsed.orgao,
                    parsed.tipo_orgao,
                    parsed.periodo_analise,
                    parsed.sat_numero,
                    parsed.site_url,
                    parsed.portal_url,
                    parsed.esic_url,
                    parsed.numero_relatorio,
                    parsed.promotoria,
                    parsed.referencia,
                    parsed.solicitacao,
                    parsed.cidade_emissao,
                    parsed.data_emissao,
                    parsed.periodo_coleta,
                    parsed.equipe_tecnica,
                    parsed.relatorio_contabil_referencia,
                    json.dumps(parsed.fontes_disponiveis),
                    json.dumps(parsed.grupos_permitidos),
                    parsed.parser_options.model_dump_json(),
                    self._dump_context_layers(parsed.context_layers),
                    generation_mode,
                    output_format,
                    parsed.database_summary,
                ),
            )
            analysis_id = int(cursor.lastrowid)
            self._replace_warnings(conn, analysis_id, parsed.warnings)
            self._replace_items(conn, analysis_id, parsed.itens_processados)
            if parsed.scraped_pages:
                self._replace_scraped_pages(conn, analysis_id, parsed.scraped_pages)
            conn.commit()
            return analysis_id

    def update_analysis(
        self,
        analysis_id: int,
        parsed: ChecklistParseResult,
        generation_mode: Optional[str] = None,
        output_format: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE analyses
                SET
                    orgao = ?,
                    tipo_orgao = ?,
                    periodo_analise = ?,
                    sat_numero = ?,
                    site_url = ?,
                    portal_url = ?,
                    esic_url = ?,
                    numero_relatorio = ?,
                    promotoria = ?,
                    referencia = ?,
                    solicitacao = ?,
                    cidade_emissao = ?,
                    data_emissao = ?,
                    periodo_coleta = ?,
                    equipe_tecnica = ?,
                    relatorio_contabil_referencia = ?,
                    fontes_disponiveis_json = ?,
                    grupos_permitidos_json = ?,
                    parser_options_json = ?,
                    context_layers_json = ?,
                    generation_mode = COALESCE(?, generation_mode),
                    output_format = COALESCE(?, output_format),
                    database_summary = ?
                WHERE id = ?
                """,
                (
                    parsed.orgao,
                    parsed.tipo_orgao,
                    parsed.periodo_analise,
                    parsed.sat_numero,
                    parsed.site_url,
                    parsed.portal_url,
                    parsed.esic_url,
                    parsed.numero_relatorio,
                    parsed.promotoria,
                    parsed.referencia,
                    parsed.solicitacao,
                    parsed.cidade_emissao,
                    parsed.data_emissao,
                    parsed.periodo_coleta,
                    parsed.equipe_tecnica,
                    parsed.relatorio_contabil_referencia,
                    json.dumps(parsed.fontes_disponiveis),
                    json.dumps(parsed.grupos_permitidos),
                    parsed.parser_options.model_dump_json(),
                    self._dump_context_layers(parsed.context_layers),
                    generation_mode,
                    output_format,
                    parsed.database_summary,
                    analysis_id,
                ),
            )
            self._replace_warnings(conn, analysis_id, parsed.warnings)
            self._replace_items(conn, analysis_id, parsed.itens_processados)
            self._replace_scraped_pages(conn, analysis_id, parsed.scraped_pages)
            conn.commit()

    def set_database_summary(self, analysis_id: int, summary: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE analyses SET database_summary = ? WHERE id = ?",
                (summary, analysis_id),
            )
            conn.commit()

    def replace_scraped_pages(self, analysis_id: int, pages: list[ScrapedPageRecord]) -> None:
        with self._connect() as conn:
            self._replace_scraped_pages(conn, analysis_id, pages)
            conn.commit()

    def record_generation(
        self,
        analysis_id: int,
        trace: GenerationTrace,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_generations (
                    analysis_id,
                    requested_mode,
                    used_mode,
                    provider,
                    model_name,
                    output_format,
                    prompt_snapshot,
                    raw_response,
                    fallback_reason,
                    duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    trace.requested_mode,
                    trace.used_mode,
                    trace.provider,
                    trace.model_name,
                    trace.output_format,
                    trace.prompt_snapshot,
                    trace.raw_response,
                    trace.fallback_reason,
                    trace.duration_ms,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def list_generations(self, analysis_id: int) -> list[GenerationTrace]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    requested_mode,
                    used_mode,
                    provider,
                    model_name,
                    output_format,
                    prompt_snapshot,
                    raw_response,
                    fallback_reason,
                    duration_ms,
                    created_at
                FROM analysis_generations
                WHERE analysis_id = ?
                ORDER BY id DESC
                """,
                (analysis_id,),
            ).fetchall()
        return [
            GenerationTrace(
                id=row["id"],
                requested_mode=row["requested_mode"],
                used_mode=row["used_mode"],
                provider=row["provider"],
                model_name=row["model_name"],
                output_format=row["output_format"],
                prompt_snapshot=row["prompt_snapshot"],
                raw_response=row["raw_response"],
                fallback_reason=row["fallback_reason"],
                duration_ms=row["duration_ms"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_analysis(self, analysis_id: int) -> Optional[ChecklistParseResult]:
        with self._connect() as conn:
            analysis_row = conn.execute(
                "SELECT * FROM analyses WHERE id = ?",
                (analysis_id,),
            ).fetchone()
            if analysis_row is None:
                return None

            parsed = ChecklistParseResult(
                analysis_id=int(analysis_row["id"]),
                orgao=analysis_row["orgao"],
                tipo_orgao=analysis_row["tipo_orgao"],
                periodo_analise=analysis_row["periodo_analise"],
                sat_numero=analysis_row["sat_numero"],
                site_url=analysis_row["site_url"],
                portal_url=analysis_row["portal_url"],
                esic_url=analysis_row["esic_url"],
                numero_relatorio=analysis_row["numero_relatorio"],
                promotoria=analysis_row["promotoria"],
                referencia=analysis_row["referencia"],
                solicitacao=analysis_row["solicitacao"],
                cidade_emissao=analysis_row["cidade_emissao"],
                data_emissao=analysis_row["data_emissao"],
                periodo_coleta=analysis_row["periodo_coleta"],
                equipe_tecnica=analysis_row["equipe_tecnica"],
                relatorio_contabil_referencia=analysis_row["relatorio_contabil_referencia"],
                fontes_disponiveis=self._load_json_list(analysis_row["fontes_disponiveis_json"]),
                grupos_permitidos=self._load_json_list(analysis_row["grupos_permitidos_json"]) or ["1", "5"],
                parser_options=self._load_parser_options(analysis_row["parser_options_json"]),
                context_layers=self._load_context_layers(analysis_row["context_layers_json"]),
                database_summary=analysis_row["database_summary"],
                warnings=[
                    row["warning"]
                    for row in conn.execute(
                        "SELECT warning FROM analysis_warnings WHERE analysis_id = ? ORDER BY id",
                        (analysis_id,),
                    ).fetchall()
                ],
                itens_processados=self._load_items(conn, analysis_id),
                scraped_pages=self._load_scraped_pages(conn, analysis_id),
            )
            return parsed

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    source_filename TEXT,
                    orgao TEXT,
                    tipo_orgao TEXT,
                    periodo_analise TEXT,
                    sat_numero TEXT,
                    site_url TEXT,
                    portal_url TEXT,
                    esic_url TEXT,
                    numero_relatorio TEXT,
                    promotoria TEXT,
                    referencia TEXT,
                    solicitacao TEXT,
                    cidade_emissao TEXT,
                    data_emissao TEXT,
                    periodo_coleta TEXT,
                    equipe_tecnica TEXT,
                    relatorio_contabil_referencia TEXT,
                    fontes_disponiveis_json TEXT,
                    grupos_permitidos_json TEXT,
                    parser_options_json TEXT,
                    context_layers_json TEXT,
                    generation_mode TEXT,
                    output_format TEXT,
                    database_summary TEXT
                );

                CREATE TABLE IF NOT EXISTS analysis_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    warning TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    grupo TEXT NOT NULL,
                    item_codigo TEXT NOT NULL,
                    linha_referencia INTEGER NOT NULL,
                    ano_referencia TEXT,
                    status TEXT NOT NULL,
                    status_2024 TEXT,
                    status_2025 TEXT,
                    fonte TEXT NOT NULL,
                    fonte_texto TEXT,
                    descricao_item TEXT NOT NULL,
                    observacao TEXT,
                    fundamentacao TEXT,
                    aba_origem TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_item_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_item_id INTEGER NOT NULL,
                    descricao TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (analysis_item_id) REFERENCES analysis_items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scraped_pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    fonte TEXT NOT NULL,
                    requested_url TEXT NOT NULL,
                    final_url TEXT NOT NULL,
                    page_title TEXT,
                    summary TEXT NOT NULL,
                    discovery_depth INTEGER NOT NULL DEFAULT 0,
                    page_score INTEGER NOT NULL DEFAULT 0,
                    discovered_from_url TEXT,
                    discovered_from_label TEXT,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scraped_page_warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id INTEGER NOT NULL,
                    warning TEXT NOT NULL,
                    FOREIGN KEY (page_id) REFERENCES scraped_pages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS scraped_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    url TEXT NOT NULL,
                    category TEXT NOT NULL,
                    destination_type TEXT NOT NULL,
                    context TEXT,
                    section TEXT,
                    is_internal INTEGER NOT NULL DEFAULT 0,
                    score INTEGER NOT NULL DEFAULT 0,
                    matched_terms_json TEXT,
                    evidence_summary TEXT,
                    FOREIGN KEY (page_id) REFERENCES scraped_pages(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS analysis_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    requested_mode TEXT NOT NULL,
                    used_mode TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_name TEXT,
                    output_format TEXT NOT NULL,
                    prompt_snapshot TEXT,
                    raw_response TEXT,
                    fallback_reason TEXT,
                    duration_ms INTEGER,
                    FOREIGN KEY (analysis_id) REFERENCES analyses(id) ON DELETE CASCADE
                );
                """
            )
            self._ensure_column(conn, "analyses", "parser_options_json", "TEXT")
            self._ensure_column(conn, "analyses", "context_layers_json", "TEXT")
            self._ensure_column(conn, "scraped_pages", "discovery_depth", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "scraped_pages", "page_score", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "scraped_pages", "discovered_from_url", "TEXT")
            self._ensure_column(conn, "scraped_pages", "discovered_from_label", "TEXT")
            self._ensure_column(conn, "scraped_links", "score", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "scraped_links", "matched_terms_json", "TEXT")
            self._ensure_column(conn, "scraped_links", "evidence_summary", "TEXT")
            self._ensure_column(conn, "analysis_generations", "duration_ms", "INTEGER")
            conn.commit()

    def _replace_warnings(
        self,
        conn: sqlite3.Connection,
        analysis_id: int,
        warnings: list[str],
    ) -> None:
        conn.execute("DELETE FROM analysis_warnings WHERE analysis_id = ?", (analysis_id,))
        conn.executemany(
            "INSERT INTO analysis_warnings (analysis_id, warning) VALUES (?, ?)",
            [(analysis_id, warning) for warning in warnings],
        )

    def _replace_items(
        self,
        conn: sqlite3.Connection,
        analysis_id: int,
        items: list[ChecklistItem],
    ) -> None:
        item_rows = conn.execute(
            "SELECT id FROM analysis_items WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchall()
        item_ids = [row["id"] for row in item_rows]
        if item_ids:
            conn.executemany(
                "DELETE FROM analysis_item_details WHERE analysis_item_id = ?",
                [(item_id,) for item_id in item_ids],
            )
        conn.execute("DELETE FROM analysis_items WHERE analysis_id = ?", (analysis_id,))

        for item in items:
            cursor = conn.execute(
                """
                INSERT INTO analysis_items (
                    analysis_id,
                    grupo,
                    item_codigo,
                    linha_referencia,
                    ano_referencia,
                    status,
                    status_2024,
                    status_2025,
                    fonte,
                    fonte_texto,
                    descricao_item,
                    observacao,
                    fundamentacao,
                    aba_origem
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    item.grupo,
                    item.item_codigo,
                    item.linha_referencia,
                    item.ano_referencia,
                    item.status,
                    item.status_2024,
                    item.status_2025,
                    item.fonte,
                    item.fonte_texto,
                    item.descricao_item,
                    item.observacao,
                    item.fundamentacao,
                    item.aba_origem,
                ),
            )
            analysis_item_id = int(cursor.lastrowid)
            conn.executemany(
                """
                INSERT INTO analysis_item_details (analysis_item_id, descricao, status)
                VALUES (?, ?, ?)
                """,
                [
                    (analysis_item_id, detail.descricao, detail.status)
                    for detail in item.detalhes
                ],
            )

    def _replace_scraped_pages(
        self,
        conn: sqlite3.Connection,
        analysis_id: int,
        pages: list[ScrapedPageRecord],
    ) -> None:
        page_rows = conn.execute(
            "SELECT id FROM scraped_pages WHERE analysis_id = ?",
            (analysis_id,),
        ).fetchall()
        page_ids = [row["id"] for row in page_rows]
        if page_ids:
            conn.executemany(
                "DELETE FROM scraped_page_warnings WHERE page_id = ?",
                [(page_id,) for page_id in page_ids],
            )
            conn.executemany(
                "DELETE FROM scraped_links WHERE page_id = ?",
                [(page_id,) for page_id in page_ids],
            )
        conn.execute("DELETE FROM scraped_pages WHERE analysis_id = ?", (analysis_id,))

        for page in pages:
            cursor = conn.execute(
                """
                INSERT INTO scraped_pages (
                    analysis_id,
                    fonte,
                    requested_url,
                    final_url,
                    page_title,
                    summary,
                    discovery_depth,
                    page_score,
                    discovered_from_url,
                    discovered_from_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    page.fonte,
                    page.requested_url,
                    page.final_url,
                    page.page_title,
                    page.summary,
                    page.discovery_depth,
                    page.page_score,
                    page.discovered_from_url,
                    page.discovered_from_label,
                ),
            )
            page_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT INTO scraped_page_warnings (page_id, warning) VALUES (?, ?)",
                [(page_id, warning) for warning in page.warnings],
            )
            conn.executemany(
                """
                INSERT INTO scraped_links (
                    page_id,
                    label,
                    url,
                    category,
                    destination_type,
                    context,
                    section,
                    is_internal,
                    score,
                    matched_terms_json,
                    evidence_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        page_id,
                        link.label,
                        link.url,
                        link.category,
                        link.destination_type,
                        link.context,
                        link.section,
                        1 if link.is_internal else 0,
                        link.score,
                        json.dumps(link.matched_terms),
                        link.evidence_summary,
                    )
                    for link in page.links
                ],
            )

    def _load_items(self, conn: sqlite3.Connection, analysis_id: int) -> list[ChecklistItem]:
        item_rows = conn.execute(
            "SELECT * FROM analysis_items WHERE analysis_id = ? ORDER BY id",
            (analysis_id,),
        ).fetchall()
        items: list[ChecklistItem] = []
        for item_row in item_rows:
            detail_rows = conn.execute(
                "SELECT descricao, status FROM analysis_item_details WHERE analysis_item_id = ? ORDER BY id",
                (item_row["id"],),
            ).fetchall()
            items.append(
                ChecklistItem(
                    grupo=item_row["grupo"],
                    item_codigo=item_row["item_codigo"],
                    linha_referencia=item_row["linha_referencia"],
                    ano_referencia=item_row["ano_referencia"],
                    status=item_row["status"],
                    status_2024=item_row["status_2024"],
                    status_2025=item_row["status_2025"],
                    fonte=item_row["fonte"],
                    fonte_texto=item_row["fonte_texto"],
                    descricao_item=item_row["descricao_item"],
                    observacao=item_row["observacao"],
                    fundamentacao=item_row["fundamentacao"],
                    detalhes=[
                        ChecklistDetail(descricao=detail["descricao"], status=detail["status"])
                        for detail in detail_rows
                    ],
                    aba_origem=item_row["aba_origem"],
                )
            )
        return items

    def _load_scraped_pages(
        self,
        conn: sqlite3.Connection,
        analysis_id: int,
    ) -> list[ScrapedPageRecord]:
        page_rows = conn.execute(
            "SELECT * FROM scraped_pages WHERE analysis_id = ? ORDER BY id",
            (analysis_id,),
        ).fetchall()
        pages: list[ScrapedPageRecord] = []
        for page_row in page_rows:
            link_rows = conn.execute(
                "SELECT * FROM scraped_links WHERE page_id = ? ORDER BY id",
                (page_row["id"],),
            ).fetchall()
            warning_rows = conn.execute(
                "SELECT warning FROM scraped_page_warnings WHERE page_id = ? ORDER BY id",
                (page_row["id"],),
            ).fetchall()
            pages.append(
                ScrapedPageRecord(
                    fonte=page_row["fonte"],
                    requested_url=page_row["requested_url"],
                    final_url=page_row["final_url"],
                    page_title=page_row["page_title"],
                    summary=page_row["summary"],
                    discovery_depth=int(page_row["discovery_depth"] or 0),
                    page_score=int(page_row["page_score"] or 0),
                    discovered_from_url=page_row["discovered_from_url"],
                    discovered_from_label=page_row["discovered_from_label"],
                    links=[
                        ScrapedLink(
                            label=link_row["label"],
                            url=link_row["url"],
                            category=link_row["category"],
                            destination_type=link_row["destination_type"],
                            context=link_row["context"],
                            section=link_row["section"],
                            is_internal=bool(link_row["is_internal"]),
                            score=int(link_row["score"] or 0),
                            matched_terms=self._load_json_list(link_row["matched_terms_json"]),
                            evidence_summary=link_row["evidence_summary"],
                        )
                        for link_row in link_rows
                    ],
                    warnings=[warning_row["warning"] for warning_row in warning_rows],
                )
            )
        return pages

    def _load_json_list(self, value: Optional[str]) -> list[str]:
        if not value:
            return []
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(loaded, list):
            return [str(item) for item in loaded]
        return []

    def _load_parser_options(self, value: Optional[str]) -> ParserOptions:
        if not value:
            return ParserOptions()
        try:
            return ParserOptions.model_validate_json(value)
        except ValueError:
            return ParserOptions()

    def _dump_context_layers(self, layers: list[WorkbookContextLayer]) -> str:
        return json.dumps(
            [layer.model_dump(mode="json") for layer in layers],
            ensure_ascii=False,
        )

    def _load_context_layers(self, value: Optional[str]) -> list[WorkbookContextLayer]:
        if not value:
            return []
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return []
        if not isinstance(loaded, list):
            return []

        layers: list[WorkbookContextLayer] = []
        for item in loaded:
            try:
                layers.append(WorkbookContextLayer.model_validate(item))
            except ValueError:
                continue
        return layers

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        if any(column["name"] == column_name for column in columns):
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
