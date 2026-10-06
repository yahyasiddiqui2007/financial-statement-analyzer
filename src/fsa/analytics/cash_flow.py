"""Cash flow metrics: how much real cash the business produces."""

from __future__ import annotations

from fsa.analytics._checks import Amount, check_inputs, divide, success
from fsa.analytics.results import MetricResult

FREE_CASH_FLOW_FORMULA = "Operating cash flow − Capital expenditures"
FCF_MARGIN_FORMULA = "(Operating cash flow − Capital expenditures) / Revenue"


def free_cash_flow(operating_cash_flow: Amount, capital_expenditures: Amount) -> MetricResult:
    """Cash left over after paying to maintain and grow the company's fixed assets.

    Sign convention: pass capital_expenditures as a POSITIVE amount spent,
    which is how SEC filings tag it (PaymentsToAcquirePropertyPlantAndEquipment).
    A negative value is rejected because it is ambiguous: it could be a sign
    mistake, and silently subtracting a negative would inflate free cash flow.

    Example: operating cash flow 500, capex 120 gives 380.

    Operating cash flow may be negative, and so may the result.
    """
    name = "free_cash_flow"
    checked = check_inputs(
        name,
        FREE_CASH_FLOW_FORMULA,
        {"operating_cash_flow": operating_cash_flow, "capital_expenditures": capital_expenditures},
        non_negative=("capital_expenditures",),
    )
    if isinstance(checked, MetricResult):
        return checked
    value = checked["operating_cash_flow"] - checked["capital_expenditures"]
    return success(name, FREE_CASH_FLOW_FORMULA, value, checked)


def fcf_margin(
    operating_cash_flow: Amount, capital_expenditures: Amount, revenue: Amount
) -> MetricResult:
    """Free cash flow as a share of revenue.

    Example: operating cash flow 500, capex 120, revenue 2,000 gives 0.19 (19%).
    """
    name = "fcf_margin"
    checked = check_inputs(
        name,
        FCF_MARGIN_FORMULA,
        {
            "operating_cash_flow": operating_cash_flow,
            "capital_expenditures": capital_expenditures,
            "revenue": revenue,
        },
        non_negative=("capital_expenditures", "revenue"),
    )
    if isinstance(checked, MetricResult):
        return checked

    fcf = checked["operating_cash_flow"] - checked["capital_expenditures"]
    return divide(
        name, FCF_MARGIN_FORMULA, fcf, checked["revenue"], checked, denominator_label="Revenue"
    )
