import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Seller Finance Deal Analyzer", layout="wide")

st.title("Seller Finance Deal Analyzer")
st.caption("Analyze cash flow, DSCR, cash-on-cash return, cap rate, seller-finance terms, and exit value.")

with st.sidebar:
    st.header("Property")
    purchase_price = st.number_input("Purchase price", min_value=0.0, value=129900.0, step=1000.0)
    arv = st.number_input("After repair value / market value", min_value=0.0, value=155000.0, step=1000.0)
    monthly_rent = st.number_input("Monthly rent", min_value=0.0, value=1227.0, step=25.0)
    other_income = st.number_input("Other monthly income", min_value=0.0, value=0.0, step=25.0)
    rehab = st.number_input("Immediate repairs / rehab", min_value=0.0, value=10000.0, step=1000.0)
    closing_costs = st.number_input("Closing costs", min_value=0.0, value=3500.0, step=500.0)

    st.header("Financing")
    down_payment_pct = st.slider("Down payment %", min_value=0.0, max_value=50.0, value=10.0, step=0.5) / 100
    interest_rate = st.slider("Interest rate %", min_value=0.0, max_value=15.0, value=6.0, step=0.25) / 100
    amort_years = st.slider("Amortization years", min_value=1, max_value=40, value=30)
    balloon_years = st.slider("Balloon / hold years", min_value=1, max_value=30, value=5)
    interest_only = st.checkbox("Interest-only payments", value=False)

    st.header("Monthly Operating Expenses")
    taxes = st.number_input("Taxes", min_value=0.0, value=183.58, step=25.0)
    insurance = st.number_input("Insurance", min_value=0.0, value=100.0, step=25.0)
    repairs_pct = st.slider("Repairs % of rent", 0.0, 20.0, 8.0, 0.5) / 100
    vacancy_pct = st.slider("Vacancy % of rent", 0.0, 20.0, 5.0, 0.5) / 100
    management_pct = st.slider("Management % of rent", 0.0, 20.0, 8.0, 0.5) / 100
    capex_pct = st.slider("CapEx % of rent", 0.0, 20.0, 5.0, 0.5) / 100
    utilities = st.number_input("Owner-paid utilities", min_value=0.0, value=0.0, step=25.0)
    hoa = st.number_input("HOA / misc.", min_value=0.0, value=0.0, step=25.0)

def pmt(rate, nper, pv):
    if pv <= 0:
        return 0.0
    if rate == 0:
        return pv / nper
    return rate * pv / (1 - (1 + rate) ** -nper)

loan_amount = purchase_price * (1 - down_payment_pct)
down_payment = purchase_price * down_payment_pct
cash_in = down_payment + rehab + closing_costs
monthly_rate = interest_rate / 12

if interest_only:
    monthly_debt = loan_amount * monthly_rate
    balance_at_balloon = loan_amount
else:
    monthly_debt = pmt(monthly_rate, amort_years * 12, loan_amount)
    balance_at_balloon = loan_amount
    for _ in range(balloon_years * 12):
        interest = balance_at_balloon * monthly_rate
        principal = max(monthly_debt - interest, 0)
        balance_at_balloon = max(balance_at_balloon - principal, 0)

gross_income = monthly_rent + other_income
repairs = monthly_rent * repairs_pct
vacancy = monthly_rent * vacancy_pct
management = monthly_rent * management_pct
capex = monthly_rent * capex_pct
opex = taxes + insurance + repairs + vacancy + management + capex + utilities + hoa

noi_monthly = gross_income - opex
cash_flow_monthly = noi_monthly - monthly_debt
noi_annual = noi_monthly * 12
cash_flow_annual = cash_flow_monthly * 12
cap_rate = noi_annual / purchase_price if purchase_price else 0
dscr = noi_monthly / monthly_debt if monthly_debt else np.inf
coc = cash_flow_annual / cash_in if cash_in else np.inf
equity_day_one = arv - purchase_price - rehab
equity_pct = equity_day_one / arv if arv else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Monthly cash flow", f"${cash_flow_monthly:,.0f}")
c2.metric("Cash-on-cash", f"{coc:.1%}")
c3.metric("DSCR", f"{dscr:.2f}")
c4.metric("Cap rate", f"{cap_rate:.1%}")

c5, c6, c7, c8 = st.columns(4)
c5.metric("Cash needed", f"${cash_in:,.0f}")
c6.metric("Monthly payment", f"${monthly_debt:,.0f}")
c7.metric("NOI / month", f"${noi_monthly:,.0f}")
c8.metric("Day-one equity", f"${equity_day_one:,.0f}", f"{equity_pct:.1%}")

st.divider()

if cash_flow_monthly >= 200 and dscr >= 1.20 and coc >= 0.10 and equity_pct >= 0:
    verdict = "Strong lead"
elif cash_flow_monthly >= 0 and dscr >= 1.00:
    verdict = "Maybe — negotiate better terms"
else:
    verdict = "Pass unless price/terms improve"

st.subheader(f"Verdict: {verdict}")

left, right = st.columns(2)

with left:
    st.subheader("Monthly breakdown")
    breakdown = pd.DataFrame({
        "Item": ["Gross income", "Taxes", "Insurance", "Repairs reserve", "Vacancy reserve", "Management", "CapEx reserve", "Utilities", "HOA / misc.", "NOI", "Debt payment", "Cash flow"],
        "Amount": [gross_income, -taxes, -insurance, -repairs, -vacancy, -management, -capex, -utilities, -hoa, noi_monthly, -monthly_debt, cash_flow_monthly]
    })
    st.dataframe(breakdown, use_container_width=True, hide_index=True)

with right:
    st.subheader("Balloon / exit")
    sale_value = st.number_input("Projected resale/refi value at balloon", min_value=0.0, value=arv, step=1000.0)
    selling_cost_pct = st.slider("Selling/refi cost %", 0.0, 12.0, 6.0, 0.5) / 100
    net_sale = sale_value * (1 - selling_cost_pct)
    exit_equity = net_sale - balance_at_balloon
    total_profit = exit_equity + cash_flow_annual * balloon_years - cash_in
    st.metric("Loan balance at balloon", f"${balance_at_balloon:,.0f}")
    st.metric("Net exit equity", f"${exit_equity:,.0f}")
    st.metric("Total estimated profit", f"${total_profit:,.0f}")

st.divider()
st.subheader("Offer helper")

target_cash_flow = st.number_input("Target monthly cash flow", min_value=0.0, value=250.0, step=25.0)
max_payment = max(noi_monthly - target_cash_flow, 0)
if interest_only:
    max_loan = max_payment / monthly_rate if monthly_rate else 0
else:
    factor = pmt(monthly_rate, amort_years * 12, 1)
    max_loan = max_payment / factor if factor else 0

max_offer = max_loan / (1 - down_payment_pct) if down_payment_pct < 1 else 0
st.write(f"To hit **${target_cash_flow:,.0f}/mo** cash flow with these terms, max offer is roughly **${max_offer:,.0f}**.")

csv = breakdown.to_csv(index=False).encode("utf-8")
st.download_button("Download monthly breakdown CSV", csv, "deal_breakdown.csv", "text/csv")