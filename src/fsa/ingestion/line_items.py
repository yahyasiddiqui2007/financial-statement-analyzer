"""Our standard line items, and which SEC (US GAAP XBRL) tags feed each one.

Companies choose from thousands of XBRL tags, and different companies (or
the same company in different years) use different tags for the same idea.
For example, revenue has been tagged "SalesRevenueNet" before 2018 and
"RevenueFromContractWithCustomerExcludingAssessedTax" after a new revenue
accounting standard (ASC 606). This module maps all of them to one name.

Tags are listed most-preferred first. For each year we use the first tag
that has a value, and we record which tag that was.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Statement(StrEnum):
    INCOME = "income_statement"
    BALANCE = "balance_sheet"
    CASH_FLOW = "cash_flow"


class PeriodKind(StrEnum):
    # Measured over a span of time ("revenue for the year").
    DURATION = "duration"
    # Measured at one moment ("total assets on September 30").
    INSTANT = "instant"


class LineItem(StrEnum):
    # Income statement
    REVENUE = "revenue"
    COST_OF_REVENUE = "cost_of_revenue"
    GROSS_PROFIT = "gross_profit"
    OPERATING_INCOME = "operating_income"
    NET_INCOME = "net_income"
    # Balance sheet
    CASH_AND_EQUIVALENTS = "cash_and_equivalents"
    SHORT_TERM_INVESTMENTS = "short_term_investments"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    INVENTORY = "inventory"
    CURRENT_ASSETS = "current_assets"
    TOTAL_ASSETS = "total_assets"
    CURRENT_LIABILITIES = "current_liabilities"
    TOTAL_LIABILITIES = "total_liabilities"
    DEBT_CURRENT = "debt_current"
    LONG_TERM_DEBT_CURRENT = "long_term_debt_current"
    COMMERCIAL_PAPER = "commercial_paper"
    SHORT_TERM_BORROWINGS = "short_term_borrowings"
    LONG_TERM_DEBT_NONCURRENT = "long_term_debt_noncurrent"
    TOTAL_DEBT = "total_debt"
    TOTAL_EQUITY = "total_equity"
    # Cash flow statement
    OPERATING_CASH_FLOW = "operating_cash_flow"
    CAPITAL_EXPENDITURES = "capital_expenditures"
    INVESTING_CASH_FLOW = "investing_cash_flow"
    FINANCING_CASH_FLOW = "financing_cash_flow"


@dataclass(frozen=True, slots=True)
class LineItemDefinition:
    item: LineItem
    statement: Statement
    label: str
    # US GAAP tags, most preferred first. Empty for items we only derive.
    tags: tuple[str, ...]

    @property
    def kind(self) -> PeriodKind:
        return PeriodKind.INSTANT if self.statement is Statement.BALANCE else PeriodKind.DURATION


def _define(item: LineItem, statement: Statement, label: str, *tags: str) -> LineItemDefinition:
    return LineItemDefinition(item=item, statement=statement, label=label, tags=tags)


_IS, _BS, _CF = Statement.INCOME, Statement.BALANCE, Statement.CASH_FLOW

DEFINITIONS: dict[LineItem, LineItemDefinition] = {
    d.item: d
    for d in [
        # --- Income statement ---
        # "Revenues" first: when a company has both contract revenue and other
        # revenue (e.g. leasing), "Revenues" is the total.
        _define(
            LineItem.REVENUE,
            _IS,
            "Revenue",
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
        ),
        _define(
            LineItem.COST_OF_REVENUE,
            _IS,
            "Cost of revenue",
            "CostOfRevenue",
            "CostOfGoodsAndServicesSold",
            "CostOfGoodsSold",
        ),
        # Derived as revenue − cost of revenue when not reported (see normalize.py).
        _define(LineItem.GROSS_PROFIT, _IS, "Gross profit", "GrossProfit"),
        _define(LineItem.OPERATING_INCOME, _IS, "Operating income", "OperatingIncomeLoss"),
        # Net income attributable to the parent company's shareholders, which
        # matches StockholdersEquity below (both exclude noncontrolling interests).
        _define(LineItem.NET_INCOME, _IS, "Net income", "NetIncomeLoss"),
        # --- Balance sheet ---
        _define(
            LineItem.CASH_AND_EQUIVALENTS,
            _BS,
            "Cash and cash equivalents",
            "CashAndCashEquivalentsAtCarryingValue",
        ),
        _define(
            LineItem.SHORT_TERM_INVESTMENTS,
            _BS,
            "Short-term investments",
            "ShortTermInvestments",
            "MarketableSecuritiesCurrent",
            "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        ),
        _define(
            LineItem.ACCOUNTS_RECEIVABLE,
            _BS,
            "Accounts receivable",
            "AccountsReceivableNetCurrent",
            "ReceivablesNetCurrent",
        ),
        _define(LineItem.INVENTORY, _BS, "Inventory", "InventoryNet"),
        _define(LineItem.CURRENT_ASSETS, _BS, "Total current assets", "AssetsCurrent"),
        _define(LineItem.TOTAL_ASSETS, _BS, "Total assets", "Assets"),
        _define(
            LineItem.CURRENT_LIABILITIES, _BS, "Total current liabilities", "LiabilitiesCurrent"
        ),
        _define(LineItem.TOTAL_LIABILITIES, _BS, "Total liabilities", "Liabilities"),
        # Debt pieces. "DebtCurrent" already includes the other three current pieces.
        _define(LineItem.DEBT_CURRENT, _BS, "Total current debt", "DebtCurrent"),
        _define(
            LineItem.LONG_TERM_DEBT_CURRENT,
            _BS,
            "Current portion of long-term debt",
            "LongTermDebtCurrent",
        ),
        _define(LineItem.COMMERCIAL_PAPER, _BS, "Commercial paper", "CommercialPaper"),
        _define(
            LineItem.SHORT_TERM_BORROWINGS, _BS, "Short-term borrowings", "ShortTermBorrowings"
        ),
        _define(
            LineItem.LONG_TERM_DEBT_NONCURRENT,
            _BS,
            "Long-term debt (non-current)",
            "LongTermDebtNoncurrent",
        ),
        # Always derived from the debt pieces above (see normalize.py).
        _define(LineItem.TOTAL_DEBT, _BS, "Total debt"),
        _define(LineItem.TOTAL_EQUITY, _BS, "Total shareholders' equity", "StockholdersEquity"),
        # --- Cash flow statement ---
        _define(
            LineItem.OPERATING_CASH_FLOW,
            _CF,
            "Cash from operating activities",
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
        # Reported as a positive number (cash paid), matching the calculation engine.
        _define(
            LineItem.CAPITAL_EXPENDITURES,
            _CF,
            "Capital expenditures",
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ),
        _define(
            LineItem.INVESTING_CASH_FLOW,
            _CF,
            "Cash from investing activities",
            "NetCashProvidedByUsedInInvestingActivities",
            "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations",
        ),
        _define(
            LineItem.FINANCING_CASH_FLOW,
            _CF,
            "Cash from financing activities",
            "NetCashProvidedByUsedInFinancingActivities",
            "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations",
        ),
    ]
}

# Every tag we care about, so the parser can skip the hundreds we don't use.
ALL_TAGS: frozenset[str] = frozenset(tag for d in DEFINITIONS.values() for tag in d.tags)
