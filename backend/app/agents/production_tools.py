"""Production tool set for the AML analysis agents (PRD-B §2).

Four tools over real data stores, plus the existing ``search_aml_corpus`` RAG tool
(:mod:`app.agents.tools`), bundled by :func:`build_production_tools`:

- ``query_accounts`` / ``query_transactions`` — parameterised reads over the tabular
  SQLite (IBM AML Kaggle data; ground-truth labels never exposed).
- ``sanctions_check`` — name screening against the downloaded OFAC SDN, HM Treasury/OFSI
  and UN Security Council consolidated lists.
- ``country_risk`` — FATF call-for-action / increased-monitoring jurisdiction lookup.

Every builder closes over an injected system (dependency inversion, mirroring
:func:`app.agents.tools.build_rag_tool`) and formats results as plain strings, since LLM
tool outputs must be content blocks. This module is the *production* tool set injected
into the shared agent modules (``app.agents.single`` / ``app.agents.mas``); the
experiment harness injects DFAH's mocked tools into the same modules instead — the two
sets never mix (PRD-A/PRD-B contract).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.ingestion.rag import RagSystem
from app.ingestion.tabular import TabularSystem
from app.ingestion.watchlists import SanctionsMatch, WatchlistSystem, normalize_name

from .tools import build_rag_tool

# Cap remark/free-text fields so a single hit can't blow up the agent context window.
_REMARKS_MAX_CHARS = 300

# Known country/jurisdiction names + common aliases, used by ``country_risk`` to tell a
# plausible-but-unlisted jurisdiction ("Germany" → not_listed) apart from input that is
# not a jurisdiction at all (agents were observed passing bank names like
# "Oasis Bancorp" and reading the resulting not_listed as a clean screen). Compared via
# the same ``normalize_name`` as the FATF lookup itself. Not exhaustive of every
# historical spelling — FATF-listed jurisdictions match the FATF lists before this
# guard is consulted, so a gap here can only turn a true not_listed into an explicit
# "unrecognised input" message, never mask a real FATF hit.
_KNOWN_COUNTRIES_AND_ALIASES: frozenset[str] = frozenset(
    normalize_name(name)
    for name in (
        # UN member/observer states and commonly screened territories
        "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda",
        "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas",
        "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin",
        "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei",
        "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon",
        "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia",
        "Comoros", "Congo", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czech Republic",
        "Democratic Republic of the Congo", "Denmark", "Djibouti", "Dominica",
        "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea",
        "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France",
        "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada",
        "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras",
        "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland",
        "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya",
        "Kiribati", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho",
        "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar",
        "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands",
        "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco",
        "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia",
        "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger",
        "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan",
        "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru",
        "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda",
        "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines",
        "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal",
        "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia",
        "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan",
        "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria",
        "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga",
        "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu",
        "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom",
        "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City",
        "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
        # Dependent territories / financial centres commonly seen in AML casework
        "Anguilla", "Aruba", "Bermuda", "British Virgin Islands", "Cayman Islands",
        "Curacao", "Gibraltar", "Greenland", "Guernsey", "Hong Kong", "Isle of Man",
        "Jersey", "Kosovo", "Macau", "Montserrat", "New Caledonia", "Puerto Rico",
        "Sint Maarten", "Taiwan", "Turks and Caicos Islands",
        # Common aliases, abbreviations and alternative spellings
        "America", "Bosnia", "Britain", "Brunei Darussalam", "Burma", "Cape Verde",
        "Cote d'Ivoire", "Czechia", "DPRK", "DR Congo", "DRC", "East Timor",
        "Great Britain", "Holland", "Ivory Coast", "Korea", "Lao PDR", "Macao",
        "Macedonia", "Republic of Korea", "Russian Federation", "Slovak Republic",
        "Swaziland", "Turkiye", "UAE", "UK", "US", "USA", "United States of America",
        "Vatican", "Viet Nam",
    )
)

_COUNTRY_RISK_UNRECOGNISED_MSG = (
    "Input {value!r} does not look like a country/jurisdiction (no match in the "
    "known-country aliases), so no FATF-list status can be given. Note that the IBM "
    "AML dataset carries no jurisdiction/country column — bank names, entity names "
    "and account/bank ids are NOT jurisdictions and must not be passed to this tool. "
    "If you cannot establish a jurisdiction from the available data, treat it as a "
    "data gap rather than as a clean ('not_listed') screening result."
)


class QueryAccountsArgs(BaseModel):
    """Arguments for the ``query_accounts`` tool."""

    account_number: Optional[str] = Field(
        default=None, description="Exact account number to look up (string; may carry leading zeros)."
    )
    bank_id: Optional[str] = Field(default=None, description="Exact bank id to filter on.")
    entity_name: Optional[str] = Field(
        default=None, description="Case-insensitive substring of the owning entity's name."
    )
    limit: int = Field(default=20, description="Maximum rows to return.")


class QueryTransactionsArgs(BaseModel):
    """Arguments for the ``query_transactions`` tool."""

    account_number: str = Field(..., description="Account number whose transactions to fetch.")
    bank_id: Optional[str] = Field(default=None, description="Restrict to this bank id.")
    direction: str = Field(
        default="both", description="'in' (account receives), 'out' (account sends) or 'both'."
    )
    min_amount: Optional[float] = Field(default=None, description="Only transactions with paid amount >= this.")
    since: Optional[str] = Field(default=None, description="ISO date/datetime lower bound, e.g. '2022-09-01'.")
    until: Optional[str] = Field(default=None, description="ISO date/datetime upper bound.")
    limit: int = Field(default=50, description="Maximum rows to return (newest first).")


class SanctionsCheckArgs(BaseModel):
    """Arguments for the ``sanctions_check`` tool."""

    name: str = Field(..., description="Individual or entity name to screen against the sanctions lists.")
    max_results: int = Field(default=5, description="Maximum matches to return.")


class CountryRiskArgs(BaseModel):
    """Arguments for the ``country_risk`` tool."""

    country: str = Field(..., description="Country or jurisdiction name to look up on the FATF lists.")


def _parse_iso(value: Optional[str], field_name: str) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date/datetime, got {value!r}") from exc


def build_query_accounts_tool(tabular: TabularSystem) -> StructuredTool:
    """Build ``query_accounts``, closing over the injected :class:`TabularSystem`."""

    def query_accounts(
        account_number: Optional[str] = None,
        bank_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        if account_number is None and bank_id is None and entity_name is None:
            return "Provide at least one filter (account_number, bank_id or entity_name)."
        rows = tabular.query_accounts(
            account_number=account_number, bank_id=bank_id, entity_name=entity_name, limit=limit
        )
        if not rows:
            return "No matching accounts found."
        return json.dumps({"accounts": rows, "row_ids": [r["id"] for r in rows]}, ensure_ascii=False)

    return StructuredTool.from_function(
        func=query_accounts,
        name="query_accounts",
        description=(
            "Look up bank accounts in the AML transactions database by account number, bank id "
            "and/or owning-entity name. Returns account rows (with row ids for the audit trail). "
            "Use this first to confirm the account under investigation exists and who owns it."
        ),
        args_schema=QueryAccountsArgs,
    )


def build_query_transactions_tool(tabular: TabularSystem) -> StructuredTool:
    """Build ``query_transactions``, closing over the injected :class:`TabularSystem`."""

    def query_transactions(
        account_number: str,
        bank_id: Optional[str] = None,
        direction: str = "both",
        min_amount: Optional[float] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 50,
    ) -> str:
        rows = tabular.query_transactions(
            account_number=account_number,
            bank_id=bank_id,
            direction=direction,
            min_amount=min_amount,
            since=_parse_iso(since, "since"),
            until=_parse_iso(until, "until"),
            limit=limit,
        )
        if not rows:
            return "No matching transactions found."
        return json.dumps({"transactions": rows, "row_ids": [r["id"] for r in rows]}, ensure_ascii=False)

    return StructuredTool.from_function(
        func=query_transactions,
        name="query_transactions",
        description=(
            "Fetch transactions for one account from the AML transactions database (newest first), "
            "optionally filtered by direction ('in'/'out'/'both'), minimum amount and ISO date range. "
            "Returns transaction rows with row ids for the audit trail. Use it to inspect volumes, "
            "counterparties, currencies and payment formats around the account under investigation."
        ),
        args_schema=QueryTransactionsArgs,
    )


def _format_sanctions_match(match: SanctionsMatch) -> dict:
    entry = match.entry
    remarks = entry.remarks
    if len(remarks) > _REMARKS_MAX_CHARS:
        remarks = remarks[: _REMARKS_MAX_CHARS - 1] + "…"
    return {
        "list": entry.list_name,
        "entry_id": entry.entry_id,
        "name": entry.name,
        "type": entry.entity_type,
        "programs": list(entry.programs),
        "match_type": match.match_type,
        "score": match.score,
        "remarks": remarks,
    }


def build_sanctions_check_tool(watchlists: WatchlistSystem) -> StructuredTool:
    """Build ``sanctions_check``, closing over the injected :class:`WatchlistSystem`."""

    def sanctions_check(name: str, max_results: int = 5) -> str:
        matches = watchlists.screen_name(name, max_results=max_results)
        if not matches:
            return f"No sanctions-list matches for '{name}' (OFAC SDN, HM Treasury, UN consolidated lists)."
        return json.dumps(
            {"query": name, "matches": [_format_sanctions_match(m) for m in matches]}, ensure_ascii=False
        )

    return StructuredTool.from_function(
        func=sanctions_check,
        name="sanctions_check",
        description=(
            "Screen an individual or entity name against the OFAC SDN list, the HM Treasury/OFSI "
            "consolidated list and the UN Security Council consolidated list. Returns matches with "
            "list name, entry id, sanctions programme and a match score. Always screen the account "
            "holder and significant counterparties before deciding."
        ),
        args_schema=SanctionsCheckArgs,
    )


def build_country_risk_tool(watchlists: WatchlistSystem) -> StructuredTool:
    """Build ``country_risk``, closing over the injected :class:`WatchlistSystem`."""

    def country_risk(country: str) -> str:
        risk = watchlists.country_risk(country)
        # Misuse guard: a not_listed answer for input that is not a jurisdiction at
        # all (e.g. a bank name) reads as a falsely clean screen. FATF hits are
        # checked first above, so this guard can never mask a listed jurisdiction.
        if risk.status == "not_listed" and normalize_name(country) not in _KNOWN_COUNTRIES_AND_ALIASES:
            return _COUNTRY_RISK_UNRECOGNISED_MSG.format(value=country)
        return json.dumps(
            {
                "country": risk.country,
                "matched_jurisdiction": risk.matched_jurisdiction,
                "status": risk.status,
                "list_date": risk.list_date,
                "source": risk.source,
            },
            ensure_ascii=False,
        )

    return StructuredTool.from_function(
        func=country_risk,
        name="country_risk",
        description=(
            "Look up a country/jurisdiction on the FATF lists. Returns status "
            "'call_for_action' (FATF black list — apply counter-measures / enhanced due diligence), "
            "'increased_monitoring' (FATF grey list — factor into risk-based assessment) or "
            "'not_listed'. Pass ONLY country/jurisdiction names (e.g. 'Iran', 'United Kingdom') — "
            "never bank or entity names; unrecognised input returns an explicit warning instead of "
            "a status. Note: the IBM AML dataset has no country column, so jurisdictions cannot be "
            "derived from account or bank ids."
        ),
        args_schema=CountryRiskArgs,
    )


def build_production_tools(
    rag: RagSystem, tabular: TabularSystem, watchlists: WatchlistSystem
) -> list[StructuredTool]:
    """Build the full production tool set for injection into the shared agent modules.

    Order is stable (data tools, screening tools, rulebook retrieval) so trajectories
    remain comparable across runs.
    """
    return [
        build_query_accounts_tool(tabular),
        build_query_transactions_tool(tabular),
        build_sanctions_check_tool(watchlists),
        build_country_risk_tool(watchlists),
        build_rag_tool(rag),
    ]
