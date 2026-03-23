from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pypdf import PdfReader

from ..models import (
    ChecklistParseResult,
    FinancialEntry,
    FinancialPeriodSummary,
    FinancialSectionSnapshot,
    ParserOptions,
    WorkbookContextLayer,
)
from .financial_workbook_parser import FinancialWorkbookParser


TRANSACTION_LINE_RE = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<history>.+?)\s+(?P<sign>[+-])?\s*R\$\s*(?P<amount>[\d\.,]+)\s*$"
)
ENTITY_HEADER_RE = re.compile(
    r"^(?P<entity>.+?)\s+Ag[eê]ncia:\s*(?P<agency>\d+)\s+Conta:\s*(?P<account>[\d\-]+)\s*$",
    re.IGNORECASE,
)
MONTH_LABELS = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}
FIXED_COST_TOKENS = (
    "mensalidade_de_seguro",
    "mensalidade_pacote_servicos",
    "pacote_servicos",
    "vida_grupo",
)
OTHER_INCOME_TOKENS = ("rendimento", "estorno", "credito", "juros")
BANK_FEE_TOKENS = (
    "tarifa",
    "tar_",
    "deb_custas",
    "custas_cartorarias",
    "comissao_recurso_nao_disp",
    "baixa_cob",
    "envio_tit",
    "prorrog_vcto",
    "reg_tit",
)
COMPANY_TOKENS = {
    "ltda",
    "servicos",
    "servico",
    "epp",
    "me",
    "mei",
    "sa",
    "s_a",
    "distribuidor",
    "modulo",
    "versa",
    "construtivo",
    "banco",
    "cartao",
}
SIGNATURE_TOKENS = ("saldo_do_dia", "pix_enviado", "pix_recebido", "historico")


def looks_like_bank_statement_pdf(statement_path: Path) -> bool:
    if statement_path.suffix.lower() != ".pdf":
        return False
    try:
        reader = PdfReader(str(statement_path))
    except Exception:
        return False
    text = "\n".join((page.extract_text() or "") for page in reader.pages[:2])
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return (
        all(token in normalized for token in SIGNATURE_TOKENS)
        or ("internet_banking" in normalized and "saldo_do_dia" in normalized and "r$" in text.lower())
    )


class BankStatementParser:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.config_entity_name_hint = ""

    def parse(self, statement_path: Path, source_name: Optional[str] = None) -> ChecklistParseResult:
        result = ChecklistParseResult(
            grupos_permitidos=[],
            parser_options=ParserOptions(
                profile=getattr(self.config, "profile", "financial_dre"),
                allowed_groups=[],
                allowed_status=[],
                checklist_sheet_name=getattr(self.config, "checklist_sheet_name", "auto"),
                metadata_row=max(1, int(getattr(self.config, "metadata_row", 5) or 5)),
            ),
            tipo_orgao="financeiro",
        )

        reader = PdfReader(str(statement_path))
        page_texts = [(page.extract_text() or "") for page in reader.pages]
        if not any(text.strip() for text in page_texts):
            result.warnings.append("O PDF nao trouxe texto selecionavel. Para extratos escaneados, sera preciso OCR.")
            return result

        source_hint = Path(source_name or statement_path.name)
        entity_name, agency, account = self._extract_header(page_texts[0], source_hint)
        result.orgao = entity_name
        self.config_entity_name_hint = entity_name or self._infer_entity_name(source_hint)

        transactions = self._extract_transactions(page_texts)
        if not transactions:
            result.warnings.append("Nenhum lancamento financeiro reconhecivel foi encontrado no extrato bancario.")
            return result

        months = self._build_months(transactions)
        helper_parser = FinancialWorkbookParser(self.config)
        analysis = helper_parser._build_financial_analysis(
            entity_name=result.orgao,
            months=months,
            summary_notes=self._build_summary_notes(
                source_name=source_hint.name,
                page_count=len(page_texts),
                transaction_count=len(transactions),
                agency=agency,
                account=account,
                months=months,
            ),
            detected_entities={
                transaction["counterparty"]
                for transaction in transactions
                if transaction.get("counterparty")
            },
        )
        analysis.workbook_kind = "bank_statement"

        result.financial_analysis = analysis
        result.periodo_analise = self._build_period_label(analysis.months)
        result.context_layers = self._build_bank_layers(
            entity_name=result.orgao,
            agency=agency,
            account=account,
            page_count=len(page_texts),
            transaction_count=len(transactions),
        ) + helper_parser._build_context_layers(analysis)
        result.warnings.extend(helper_parser._build_financial_warnings(analysis))
        if len(transactions) < 5:
            result.warnings.append("O extrato trouxe poucos lancamentos. Revise se o periodo exportado esta completo.")
        return result

    def _extract_header(self, first_page_text: str, source_hint: Path) -> tuple[str, Optional[str], Optional[str]]:
        for raw_line in first_page_text.splitlines():
            line = _sanitize_line(raw_line)
            if not line:
                continue
            match = ENTITY_HEADER_RE.match(line)
            if not match:
                continue
            return (
                match.group("entity").strip(),
                match.group("agency").strip(),
                match.group("account").strip(),
            )
        return (self._infer_entity_name(source_hint), None, None)

    def _extract_transactions(self, page_texts: list[str]) -> list[dict[str, Any]]:
        transactions: list[dict[str, Any]] = []
        for page_text in page_texts:
            for raw_line in page_text.splitlines():
                line = _sanitize_line(raw_line)
                if not line:
                    continue
                match = TRANSACTION_LINE_RE.match(line)
                if not match:
                    continue
                date_value = datetime.strptime(match.group("date"), "%d/%m/%Y")
                history = match.group("history").strip()
                amount = _parse_brazilian_currency(match.group("amount"))
                if amount is None:
                    continue
                signed_amount = amount if match.group("sign") != "-" else -amount
                normalized_history = _normalize_text(history)
                counterparty = self._extract_counterparty(history)
                transactions.append(
                    {
                        "date": date_value,
                        "history": history,
                        "normalized_history": normalized_history,
                        "amount": signed_amount,
                        "counterparty": counterparty,
                        "counterparty_key": _normalize_text(counterparty) if counterparty else None,
                    }
                )
        return transactions

    def _build_months(self, transactions: list[dict[str, Any]]) -> list[FinancialPeriodSummary]:
        grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        counterparty_counts: dict[str, int] = defaultdict(int)
        for transaction in transactions:
            date_value: datetime = transaction["date"]
            grouped[(date_value.year, date_value.month)].append(transaction)
            if transaction.get("counterparty_key"):
                counterparty_counts[transaction["counterparty_key"]] += 1

        months: list[FinancialPeriodSummary] = []
        for (year, month), month_transactions in sorted(grouped.items()):
            receivable_entries: list[FinancialEntry] = []
            other_income_entries: list[FinancialEntry] = []
            fixed_cost_entries: list[FinancialEntry] = []
            personnel_entries: list[FinancialEntry] = []
            bank_fee_entries: list[FinancialEntry] = []
            operating_cost_entries: list[FinancialEntry] = []
            internal_transfer_entries: list[FinancialEntry] = []
            closing_total: Optional[float] = None

            for transaction in sorted(month_transactions, key=lambda item: item["date"]):
                history = transaction["history"]
                normalized_history = transaction["normalized_history"]
                amount = float(transaction["amount"])
                date_label = transaction["date"].strftime("%Y-%m-%d")

                if "saldo_do_dia" in normalized_history:
                    closing_total = abs(amount)
                    continue

                classification = self._classify_transaction(transaction, counterparty_counts)
                target_list = {
                    "receivable": receivable_entries,
                    "other_income": other_income_entries,
                    "fixed_cost": fixed_cost_entries,
                    "personnel": personnel_entries,
                    "bank_fee": bank_fee_entries,
                    "operating_cost": operating_cost_entries,
                    "internal_transfer": internal_transfer_entries,
                }[classification["bucket"]]
                target_list.append(
                    self._build_entry(
                        entry_type=classification["entry_type"],
                        sheet_name=MONTH_LABELS[month],
                        history=history,
                        amount=classification["amount"],
                        date_label=date_label,
                        counterparty=transaction["counterparty"],
                        tags=classification["tags"],
                        notes=classification["note"],
                    )
                )

            receivables_total = _sum_amount(entry.amount for entry in receivable_entries) or 0.0
            other_income_total = _sum_amount(entry.amount for entry in other_income_entries) or 0.0
            fixed_costs_total = _sum_amount(entry.amount for entry in fixed_cost_entries) or 0.0
            personnel_total = _sum_amount(entry.amount for entry in personnel_entries) or 0.0
            bank_fee_total = _sum_amount(entry.amount for entry in bank_fee_entries) or 0.0
            operating_outflow_total = _sum_amount(entry.amount for entry in operating_cost_entries) or 0.0
            operating_costs_total = operating_outflow_total + bank_fee_total
            global_expenses_total = fixed_costs_total + personnel_total + operating_costs_total
            period_label = f"{MONTH_LABELS[month]}/{year}"

            sections = []
            if receivable_entries:
                sections.append(
                    FinancialSectionSnapshot(
                        section_key="receivables",
                        title="Entradas confirmadas via extrato",
                        total_amount=receivables_total,
                        entry_count=len(receivable_entries),
                        entries=receivable_entries,
                    )
                )
            if other_income_entries:
                sections.append(
                    FinancialSectionSnapshot(
                        section_key="other_income",
                        title="Entradas complementares via extrato",
                        total_amount=other_income_total,
                        entry_count=len(other_income_entries),
                        entries=other_income_entries,
                    )
                )
            if fixed_cost_entries:
                sections.append(
                    FinancialSectionSnapshot(
                        section_key="fixed_cost",
                        title="Custos fixos identificados no extrato",
                        total_amount=fixed_costs_total,
                        entry_count=len(fixed_cost_entries),
                        entries=fixed_cost_entries,
                    )
                )
            if personnel_entries:
                sections.append(
                    FinancialSectionSnapshot(
                        section_key="personnel",
                        title="Pagamentos classificados como pessoal",
                        total_amount=personnel_total,
                        entry_count=len(personnel_entries),
                        entries=personnel_entries,
                    )
                )
            if bank_fee_entries:
                sections.append(
                    FinancialSectionSnapshot(
                        section_key="bank_fee",
                        title="Tarifas e custos bancarios",
                        total_amount=bank_fee_total,
                        entry_count=len(bank_fee_entries),
                        entries=bank_fee_entries,
                    )
                )
            if operating_cost_entries:
                sections.append(
                    FinancialSectionSnapshot(
                        section_key="operating_cost",
                        title="Saidas operacionais identificadas no extrato",
                        total_amount=operating_outflow_total,
                        entry_count=len(operating_cost_entries),
                        entries=operating_cost_entries,
                    )
                )
            if internal_transfer_entries:
                sections.append(
                    FinancialSectionSnapshot(
                        section_key="summary",
                        title="Transferencias internas ou neutras (fora da DRE)",
                        total_amount=_sum_amount(entry.amount for entry in internal_transfer_entries),
                        entry_count=len(internal_transfer_entries),
                        entries=internal_transfer_entries,
                    )
                )

            months.append(
                FinancialPeriodSummary(
                    sheet_name=MONTH_LABELS[month],
                    period_label=period_label,
                    year=year,
                    gross_revenue_total=receivables_total + other_income_total,
                    receivables_total=receivables_total,
                    other_income_total=other_income_total,
                    personnel_total=personnel_total,
                    fixed_costs_total=fixed_costs_total,
                    operating_costs_total=operating_costs_total,
                    global_expenses_total=global_expenses_total,
                    net_result=(receivables_total + other_income_total) - global_expenses_total,
                    closing_total=closing_total,
                    pending_entry_count=0,
                    sections=sections,
                    notes=self._build_month_notes(
                        period_label=period_label,
                        section_count=len(sections),
                        personnel_count=len(personnel_entries),
                        bank_fee_count=len(bank_fee_entries),
                        internal_transfer_count=len(internal_transfer_entries),
                    ),
                )
            )
        return months

    def _build_entry(
        self,
        entry_type: str,
        sheet_name: str,
        history: str,
        amount: float,
        date_label: str,
        counterparty: Optional[str],
        tags: Optional[list[str]] = None,
        notes: Optional[str] = None,
    ) -> FinancialEntry:
        return FinancialEntry(
            entry_type=entry_type,
            sheet_name=sheet_name,
            description=history,
            amount=amount,
            date=date_label,
            due_date=date_label,
            counterparty=counterparty,
            tags=list(tags or []),
            notes=notes,
        )

    def _build_summary_notes(
        self,
        source_name: str,
        page_count: int,
        transaction_count: int,
        agency: Optional[str],
        account: Optional[str],
        months: list[FinancialPeriodSummary],
    ) -> list[str]:
        notes = [
            f"Extrato bancario importado de {source_name} com {page_count} pagina(s) e {transaction_count} lancamento(s) reconhecido(s)."
        ]
        if agency and account:
            notes.append(f"Conta identificada no extrato: agencia {agency}, conta {account}.")
        internal_transfer_total = _sum_amount(
            section.total_amount
            for month in months
            for section in month.sections
            if section.title == "Transferencias internas ou neutras (fora da DRE)"
        )
        personnel_total = _sum_amount(month.personnel_total for month in months)
        if internal_transfer_total:
            notes.append(
                f"Transferencias internas ou neutras excluidas da DRE: {_format_currency(internal_transfer_total)}."
            )
        if personnel_total:
            notes.append(
                f"Pagamentos classificados como pessoal no extrato: {_format_currency(personnel_total)}."
            )
        return notes

    def _build_bank_layers(
        self,
        entity_name: Optional[str],
        agency: Optional[str],
        account: Optional[str],
        page_count: int,
        transaction_count: int,
    ) -> list[WorkbookContextLayer]:
        details = [f"Paginas lidas: {page_count}", f"Lancamentos reconhecidos: {transaction_count}"]
        if agency:
            details.append(f"Agencia: {agency}")
        if account:
            details.append(f"Conta: {account}")
        return [
            WorkbookContextLayer(
                layer_type="financial_overview",
                sheet_name="Extrato bancario",
                title="Origem bancaria consolidada",
                summary=(
                    f"Extrato bancario identificado para {entity_name or 'entidade nao informada'}, "
                    f"com {transaction_count} lancamento(s) estruturado(s)."
                ),
                details=details,
            )
        ]

    def _build_month_notes(
        self,
        period_label: str,
        section_count: int,
        personnel_count: int,
        bank_fee_count: int,
        internal_transfer_count: int,
    ) -> list[str]:
        notes = [f"{period_label}: {section_count} bloco(s) classificado(s) a partir do extrato bancario."]
        if personnel_count:
            notes.append(f"{period_label}: {personnel_count} pagamento(s) foram tratados como pessoal.")
        if bank_fee_count:
            notes.append(f"{period_label}: {bank_fee_count} lancamento(s) foram tratados como tarifa ou custo bancario.")
        if internal_transfer_count:
            notes.append(f"{period_label}: {internal_transfer_count} transferencia(s) interna(s) ficaram fora da DRE.")
        return notes

    def _classify_transaction(
        self,
        transaction: dict[str, Any],
        counterparty_counts: dict[str, int],
    ) -> dict[str, Any]:
        normalized_history = transaction["normalized_history"]
        amount = float(transaction["amount"])
        absolute_amount = abs(amount)
        counterparty = transaction.get("counterparty")
        counterparty_key = transaction.get("counterparty_key")
        tags: list[str] = []
        note: Optional[str] = None

        if amount >= 0:
            if self._is_internal_counterparty(counterparty):
                return {
                    "bucket": "internal_transfer",
                    "entry_type": "internal_transfer",
                    "amount": absolute_amount,
                    "tags": ["internal_transfer", "inflow"],
                    "note": "Entrada tratada como transferencia interna e excluida da DRE.",
                }
            if any(token in normalized_history for token in OTHER_INCOME_TOKENS):
                return {
                    "bucket": "other_income",
                    "entry_type": "other_income",
                    "amount": absolute_amount,
                    "tags": ["financial_yield"],
                    "note": None,
                }
            return {
                "bucket": "receivable",
                "entry_type": "receivable",
                "amount": absolute_amount,
                "tags": ["bank_receipt"],
                "note": None,
            }

        if self._is_internal_counterparty(counterparty):
            return {
                "bucket": "internal_transfer",
                "entry_type": "internal_transfer",
                "amount": absolute_amount,
                "tags": ["internal_transfer", "outflow"],
                "note": "Saida tratada como transferencia interna e excluida da DRE.",
            }
        if any(token in normalized_history for token in FIXED_COST_TOKENS):
            return {
                "bucket": "fixed_cost",
                "entry_type": "fixed_cost",
                "amount": absolute_amount,
                "tags": ["fixed_cost"],
                "note": None,
            }
        if any(token in normalized_history for token in BANK_FEE_TOKENS):
            return {
                "bucket": "bank_fee",
                "entry_type": "bank_fee",
                "amount": absolute_amount,
                "tags": ["bank_fee"],
                "note": "Despesa bancaria classificada separadamente dentro dos custos operacionais.",
            }
        if counterparty and self._looks_like_individual_counterparty(counterparty):
            frequency = counterparty_counts.get(counterparty_key or "", 0)
            if frequency >= 2 or "pix_enviado" in normalized_history:
                tags.append("personnel_candidate")
                note = "Lancamento classificado como pessoal por recorrencia e perfil do favorecido."
                return {
                    "bucket": "personnel",
                    "entry_type": "personnel",
                    "amount": absolute_amount,
                    "tags": tags,
                    "note": note,
                }
        return {
            "bucket": "operating_cost",
            "entry_type": "operating_cost",
            "amount": absolute_amount,
            "tags": ["operational_outflow"],
            "note": None,
        }

    def _build_period_label(self, months: list[FinancialPeriodSummary]) -> Optional[str]:
        if not months:
            return None
        first_period = months[0].period_label
        last_period = months[-1].period_label
        return first_period if first_period == last_period else f"{first_period} a {last_period}"

    def _infer_entity_name(self, source_hint: Path) -> str:
        cleaned = re.sub(r"\b(extrato|pj|pdf|\d{2}_\d{2}_\d{4}|\d{2}h\d{2}m\d{2}s)\b", "", source_hint.stem, flags=re.IGNORECASE)
        cleaned = re.sub(r"[_\-]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or "Extrato bancario"

    def _extract_counterparty(self, history: str) -> Optional[str]:
        prefixes = (
            "Pix Enviado ",
            "Pix Recebido ",
            "Pagamento De Boleto Outros Bancos ",
            "Pagamento Cartao Credito ",
            "Cr Cob Bloq Comp Conf Recebimento ",
            "Cr Cob Bloq Conf Recebimento ",
        )
        for prefix in prefixes:
            if history.startswith(prefix):
                counterparty = history[len(prefix) :].strip(" -")
                return counterparty or None
        normalized_history = _normalize_text(history)
        if any(
            token in normalized_history
            for token in ("saldo_do_dia", "rendimento", "tarifa", "mensalidade", "comissao", "deb_custas")
        ):
            return None
        if self._looks_like_individual_counterparty(history):
            return history.strip(" -") or None
        history_tokens = {token for token in normalized_history.split("_") if token}
        if history_tokens & COMPANY_TOKENS:
            return history.strip(" -") or None
        return None

    def _is_internal_counterparty(self, counterparty: Optional[str]) -> bool:
        if not counterparty:
            return False
        entity_name = _normalize_text(getattr(self, "config_entity_name_hint", "") or "")
        normalized_counterparty = _normalize_text(counterparty)
        if not normalized_counterparty or not entity_name:
            return False
        if normalized_counterparty == entity_name:
            return True
        entity_tokens = [token for token in entity_name.split("_") if token and token not in COMPANY_TOKENS]
        counterparty_tokens = [token for token in normalized_counterparty.split("_") if token and token not in COMPANY_TOKENS]
        if not entity_tokens or not counterparty_tokens:
            return False
        overlap = set(entity_tokens) & set(counterparty_tokens)
        return len(overlap) >= 2 or normalized_counterparty.startswith("_".join(entity_tokens[:2]))

    def _looks_like_individual_counterparty(self, counterparty: str) -> bool:
        normalized = _normalize_text(counterparty)
        if not normalized or normalized.isdigit():
            return False
        tokens = [token for token in normalized.split("_") if token]
        if len(tokens) < 2:
            return False
        if any(token in COMPANY_TOKENS for token in tokens):
            return False
        if all(token.isdigit() for token in tokens):
            return False
        return True


def _sanitize_line(value: str) -> str:
    cleaned = value.replace("\uF12D", " ").replace("\uF228", " ").replace("\uF10A", " ")
    cleaned = cleaned.replace("", " ").replace("", " ").replace("", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned.strip()


def _normalize_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^\w_]", "", text)
    return text.strip("_")


def _parse_brazilian_currency(value: str) -> Optional[float]:
    cleaned = str(value or "").replace(".", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _sum_amount(values) -> Optional[float]:
    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return float(sum(numbers))


def _format_currency(value: Optional[float]) -> str:
    if value is None:
        return "-"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
