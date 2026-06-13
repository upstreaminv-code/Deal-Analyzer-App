import streamlit as st
import pandas as pd
import numpy as np
from io import StringIO
from datetime import date

st.set_page_config(page_title="Upstream Investments OS", layout="wide")

# -----------------------------
# Helpers
# -----------------------------

def pmt(rate, nper, pv):
    if pv <= 0:
        return 0.0
    if rate == 0:
        return pv / nper
    return rate * pv / (1 - (1 + rate) ** -nper)

def remaining_balance(loan, annual_rate, payment, months):
    bal = loan
    monthly_rate = annual_rate / 12
    for _ in range(int(months)):
        interest = bal * monthly_rate
        principal = max(payment - interest, 0)
        bal = max(bal - principal, 0)
    return bal

def grade_deal(cash_flow, dscr, coc, equity_pct):
    if cash_flow >= 400 and dscr >= 1.30 and coc >= 0.15 and equity_pct >= 0.15:
        return "A+"
    if cash_flow >= 250 and dscr >= 1.20 and coc >= 0.10 and equity_pct >= 0.10:
        return "A"
    if cash_flow >= 100 and dscr >= 1.10:
        return "B"
    if cash_flow >= 0 and dscr >= 1.00:
        return "C"
    return "Pass"

def analyze(
    price, arv, rent, other_income, rehab, closing_costs,
    down_pct, rate, amort_years, balloon_years, interest_only,
    taxes, insurance, repairs_pct, vacancy_pct, mgmt_pct, capex_pct,
    utilities, hoa
):
    loan = price * (1 - down_pct)
    cash_needed = price * down_pct + rehab + closing_costs
    monthly_rate = rate / 12

    if interest_only:
        debt = loan * monthly_rate
        balloon_balance = loan
    else:
        debt = pmt(monthly_rate, amort_years * 12, loan)
        balloon_balance = remaining_balance(loan, rate, debt, balloon_years * 12)

    gross = rent + other_income
    expenses = (
        taxes + insurance + utilities + hoa +
        rent * repairs_pct + rent * vacancy_pct + rent * mgmt_pct + rent * capex_pct
    )
    noi = gross - expenses
    cf = noi - debt
    annual_cf = cf * 12
    annual_noi = noi * 12
    dscr = noi / debt if debt else np.inf
    coc = annual_cf / cash_needed if cash_needed else np.inf
    cap = annual_noi / price if price else 0
    equity = arv - price - rehab
    equity_pct = equity / arv if arv else 0
    grade = grade_deal(cf, dscr, coc, equity_pct)

    return {
        "price": price, "arv": arv, "rent": rent, "gross_income": gross,
        "expenses": expenses, "noi": noi, "debt": debt, "cash_flow": cf,
        "annual_cash_flow": annual_cf, "dscr": dscr, "coc": coc, "cap_rate": cap,
        "cash_needed": cash_needed, "loan": loan, "equity": equity,
        "equity_pct": equity_pct, "balloon_balance": balloon_balance, "grade": grade
    }

def max_offer(rent, other_income, target_cf, down_pct, rate, amort_years, interest_only,
              taxes, insurance, repairs_pct, vacancy_pct, mgmt_pct, capex_pct, utilities, hoa):
    gross = rent + other_income
    expenses = taxes + insurance + utilities + hoa + rent*(repairs_pct+vacancy_pct+mgmt_pct+capex_pct)
    noi = gross - expenses
    max_debt = max(noi - target_cf, 0)
    monthly_rate = rate / 12
    if interest_only:
        max_loan = max_debt / monthly_rate if monthly_rate else 0
    else:
        factor = pmt(monthly_rate, amort_years*12, 1)
        max_loan = max_debt / factor if factor else 0
    return max_loan / (1 - down_pct) if down_pct < 1 else 0

def memo_text(address, result, risks, strategy):
    return f"""
# Investment Memo

## Property
{address}

## Recommendation
Grade: {result['grade']}

## Key Metrics
- Monthly Cash Flow: ${result['cash_flow']:,.0f}
- DSCR: {result['dscr']:.2f}
- Cash-on-Cash Return: {result['coc']:.1%}
- Cap Rate: {result['cap_rate']:.1%}
- Cash Needed: ${result['cash_needed']:,.0f}
- Day-One Equity: ${result['equity']:,.0f}
- Loan Balance at Balloon: ${result['balloon_balance']:,.0f}

## Strategy
{strategy}

## Risks / Due Diligence
{risks}

## Decision
{"Pursue" if result['grade'] in ["A+", "A"] else "Negotiate / Pass unless terms improve"}
"""

def loi_text(buyer, seller, address, price, down, rate, amort, balloon, close_days):
    return f"""
LETTER OF INTENT — SELLER FINANCE PURCHASE

Date: {date.today().strftime("%B %d, %Y")}

Buyer: {buyer}
Seller: {seller}
Property: {address}

Buyer proposes to purchase the Property for ${price:,.0f}.

Proposed Seller Finance Terms:
- Purchase Price: ${price:,.0f}
- Down Payment: ${down:,.0f}
- Seller-Financed Balance: ${price-down:,.0f}
- Interest Rate: {rate:.2f}%
- Amortization: {amort} years
- Balloon: {balloon} years
- Target Closing: within {close_days} days after accepted purchase agreement

Due Diligence:
This offer is subject to inspection, title review, rent verification, insurance quote, property condition review, and mutually acceptable purchase documentation.

This LOI is non-binding and intended only to outline proposed business terms.
"""

# -----------------------------
# Session state
# -----------------------------

if "deals" not in st.session_state:
    st.session_state.deals = pd.DataFrame(columns=[
        "Status","Address","Price","ARV","Rent","Grade","Cash Flow","DSCR","CoC","Cap Rate",
        "Cash Needed","Equity","Max Offer","Notes"
    ])

st.title("Upstream Investments Operating System")
st.caption("Deal analyzer, max-offer engine, CSV lead ranking, CRM, portfolio tracker, LOI generator, and investment memo builder.")

tabs = st.tabs([
    "Analyze Deal",
    "Bulk Lead Import",
    "CRM Pipeline",
    "Portfolio",
    "LOI Generator",
    "Investment Memo",
    "Capital Matching",
    "Settings / Integrations"
])

# -----------------------------
# Analyze Deal
# -----------------------------
with tabs[0]:
    st.header("Single Deal Analyzer")

    c1, c2, c3 = st.columns(3)
    with c1:
        address = st.text_input("Address", "471 Kitchener St, Detroit, MI")
        price = st.number_input("Purchase / list price", value=129900.0, step=1000.0)
        arv = st.number_input("ARV / current value", value=155000.0, step=1000.0)
        rent = st.number_input("Monthly rent", value=1227.0, step=25.0)
        other_income = st.number_input("Other monthly income", value=0.0, step=25.0)
        rehab = st.number_input("Repairs / rehab", value=10000.0, step=1000.0)
        closing = st.number_input("Closing costs", value=3500.0, step=500.0)

    with c2:
        st.subheader("Financing")
        down_pct = st.slider("Down payment %", 0.0, 50.0, 10.0, 0.5) / 100
        rate = st.slider("Interest rate %", 0.0, 15.0, 6.0, 0.25) / 100
        amort = st.slider("Amortization years", 1, 40, 30)
        balloon = st.slider("Balloon / hold years", 1, 30, 5)
        interest_only = st.checkbox("Interest only", False)

    with c3:
        st.subheader("Monthly Expenses")
        taxes = st.number_input("Taxes", value=183.58, step=25.0)
        insurance = st.number_input("Insurance", value=100.0, step=25.0)
        repairs_pct = st.slider("Repairs reserve %", 0.0, 20.0, 8.0, 0.5) / 100
        vacancy_pct = st.slider("Vacancy %", 0.0, 20.0, 5.0, 0.5) / 100
        mgmt_pct = st.slider("Management %", 0.0, 20.0, 8.0, 0.5) / 100
        capex_pct = st.slider("CapEx %", 0.0, 20.0, 5.0, 0.5) / 100
        utilities = st.number_input("Owner-paid utilities", value=0.0, step=25.0)
        hoa = st.number_input("HOA / misc.", value=0.0, step=25.0)

    result = analyze(price, arv, rent, other_income, rehab, closing, down_pct, rate, amort, balloon,
                     interest_only, taxes, insurance, repairs_pct, vacancy_pct, mgmt_pct, capex_pct,
                     utilities, hoa)

    m = st.columns(6)
    m[0].metric("Grade", result["grade"])
    m[1].metric("Cash Flow", f"${result['cash_flow']:,.0f}/mo")
    m[2].metric("DSCR", f"{result['dscr']:.2f}")
    m[3].metric("CoC", f"{result['coc']:.1%}")
    m[4].metric("Cap Rate", f"{result['cap_rate']:.1%}")
    m[5].metric("Cash Needed", f"${result['cash_needed']:,.0f}")

    m2 = st.columns(4)
    m2[0].metric("NOI", f"${result['noi']:,.0f}/mo")
    m2[1].metric("Payment", f"${result['debt']:,.0f}/mo")
    m2[2].metric("Day-One Equity", f"${result['equity']:,.0f}", f"{result['equity_pct']:.1%}")
    m2[3].metric("Balloon Balance", f"${result['balloon_balance']:,.0f}")

    st.subheader("Max Offer Engine")
    target_cf = st.number_input("Target monthly cash flow", value=250.0, step=25.0)
    offer = max_offer(rent, other_income, target_cf, down_pct, rate, amort, interest_only,
                      taxes, insurance, repairs_pct, vacancy_pct, mgmt_pct, capex_pct, utilities, hoa)
    st.metric("Maximum offer", f"${offer:,.0f}")

    notes = st.text_area("Deal notes", "Verify rent, taxes, insurance, roof, HVAC, foundation, neighborhood, and seller finance willingness.")
    if st.button("Save to CRM"):
        new = pd.DataFrame([{
            "Status":"Lead Found","Address":address,"Price":price,"ARV":arv,"Rent":rent,
            "Grade":result["grade"],"Cash Flow":result["cash_flow"],"DSCR":result["dscr"],
            "CoC":result["coc"],"Cap Rate":result["cap_rate"],"Cash Needed":result["cash_needed"],
            "Equity":result["equity"],"Max Offer":offer,"Notes":notes
        }])
        st.session_state.deals = pd.concat([st.session_state.deals, new], ignore_index=True)
        st.success("Saved to CRM.")

# -----------------------------
# Bulk
# -----------------------------
with tabs[1]:
    st.header("Bulk Lead Import")
    st.write("Upload Buy Box Cartel / PropStream / manual CSV. Required columns: address, price, rent. Optional: arv, rehab, taxes, insurance.")

    sample = pd.DataFrame({
        "address":["471 Kitchener St, Detroit, MI","213 W 110th Pl, Chicago, IL"],
        "price":[129900,64900],
        "rent":[1227,1981],
        "arv":[155000,100000],
        "rehab":[10000,25000],
        "taxes":[183.58,73.83],
        "insurance":[100,100]
    })
    st.download_button("Download sample CSV", sample.to_csv(index=False), "sample_leads.csv", "text/csv")

    file = st.file_uploader("Upload CSV", type="csv")
    if file:
        df = pd.read_csv(file)
        df.columns = [c.lower().strip() for c in df.columns]
        if not {"address","price","rent"}.issubset(df.columns):
            st.error("CSV must include address, price, rent.")
        else:
            rows = []
            for _, r in df.iterrows():
                res = analyze(
                    float(r.get("price",0)), float(r.get("arv", r.get("price",0))), float(r.get("rent",0)),
                    0, float(r.get("rehab",10000)), 3500, .10, .06, 30, 5, False,
                    float(r.get("taxes",150)), float(r.get("insurance",100)), .08, .05, .08, .05, 0, 0
                )
                mo = max_offer(float(r.get("rent",0)), 0, 250, .10, .06, 30, False,
                               float(r.get("taxes",150)), float(r.get("insurance",100)), .08, .05, .08, .05, 0, 0)
                rows.append({
                    "Status":"Lead Found","Address":r.get("address",""),"Price":res["price"],"ARV":res["arv"],
                    "Rent":res["rent"],"Grade":res["grade"],"Cash Flow":res["cash_flow"],"DSCR":res["dscr"],
                    "CoC":res["coc"],"Cap Rate":res["cap_rate"],"Cash Needed":res["cash_needed"],
                    "Equity":res["equity"],"Max Offer":mo,"Notes":"Imported lead"
                })
            out = pd.DataFrame(rows)
            grade_order = {"A+":0,"A":1,"B":2,"C":3,"Pass":4}
            out["grade_sort"] = out["Grade"].map(grade_order)
            out = out.sort_values(["grade_sort","Cash Flow"], ascending=[True,False]).drop(columns="grade_sort")
            st.dataframe(out, use_container_width=True, hide_index=True)
            st.download_button("Download analyzed leads", out.to_csv(index=False), "analyzed_leads.csv", "text/csv")
            if st.button("Add all imported leads to CRM"):
                st.session_state.deals = pd.concat([st.session_state.deals, out], ignore_index=True)
                st.success("Imported leads saved to CRM.")

# -----------------------------
# CRM
# -----------------------------
with tabs[2]:
    st.header("CRM Pipeline")
    if st.session_state.deals.empty:
        st.info("No saved deals yet. Save a deal from the analyzer or bulk import.")
    else:
        edited = st.data_editor(
            st.session_state.deals,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Lead Found","Analyzing","Offer Sent","Negotiating","Under Contract","Closed","Dead"]
                )
            }
        )
        st.session_state.deals = edited
        st.download_button("Export CRM CSV", edited.to_csv(index=False), "crm_pipeline.csv", "text/csv")

        st.subheader("Pipeline Summary")
        st.bar_chart(edited["Status"].value_counts())

# -----------------------------
# Portfolio
# -----------------------------
with tabs[3]:
    st.header("Portfolio Tracker")
    text = st.text_area(
        "Paste portfolio CSV",
        "property,value,loan_balance,monthly_cash_flow\nOmaha Duplex,350000,260000,487\nDetroit SFH,155000,108790,-77",
        height=150
    )
    try:
        port = pd.read_csv(StringIO(text))
        port["equity"] = port["value"] - port["loan_balance"]
        st.dataframe(port, use_container_width=True, hide_index=True)
        c = st.columns(4)
        c[0].metric("Total Value", f"${port['value'].sum():,.0f}")
        c[1].metric("Total Debt", f"${port['loan_balance'].sum():,.0f}")
        c[2].metric("Total Equity", f"${port['equity'].sum():,.0f}")
        c[3].metric("Monthly Cash Flow", f"${port['monthly_cash_flow'].sum():,.0f}")
    except Exception:
        st.warning("Use columns: property,value,loan_balance,monthly_cash_flow")

# -----------------------------
# LOI
# -----------------------------
with tabs[4]:
    st.header("LOI Generator")
    buyer = st.text_input("Buyer", "Upstream Investments LLC")
    seller = st.text_input("Seller", "Seller")
    loi_address = st.text_input("Property", "471 Kitchener St, Detroit, MI")
    loi_price = st.number_input("Offer price", value=118000.0, step=1000.0)
    loi_down = st.number_input("Down payment", value=10000.0, step=1000.0)
    loi_rate = st.number_input("Interest rate %", value=4.0, step=.25)
    loi_amort = st.number_input("Amortization years", value=30, step=1)
    loi_balloon = st.number_input("Balloon years", value=7, step=1)
    close_days = st.number_input("Closing days", value=45, step=5)
    loi = loi_text(buyer, seller, loi_address, loi_price, loi_down, loi_rate, loi_amort, loi_balloon, close_days)
    st.text_area("LOI", loi, height=420)
    st.download_button("Download LOI", loi, "seller_finance_loi.txt", "text/plain")

# -----------------------------
# Memo
# -----------------------------
with tabs[5]:
    st.header("Investment Memo Builder")
    risks = st.text_area("Risks / diligence", "Rent estimate needs verification. Confirm taxes, insurance, roof, HVAC, foundation, sewer, occupancy, code violations, and title.")
    strategy = st.text_area("Strategy", "Acquire with seller financing, stabilize operations, refinance or hold through balloon.")
    memo = memo_text(address if "address" in locals() else "Property", result if "result" in locals() else {
        "grade":"Pass","cash_flow":0,"dscr":0,"coc":0,"cap_rate":0,"cash_needed":0,"equity":0,"balloon_balance":0
    }, risks, strategy)
    st.markdown(memo)
    st.download_button("Download memo", memo, "investment_memo.md", "text/markdown")

# -----------------------------
# Capital
# -----------------------------
with tabs[6]:
    st.header("Capital Matching")
    investor_csv = st.text_area(
        "Investor CSV",
        "investor,available_capital,target_return,notes\nInvestor A,100000,10%,Prefers Midwest rentals\nInvestor B,250000,12%,Open to seller finance deals"
    )
    capital_needed = st.number_input("Capital needed for selected deal", value=35000.0, step=1000.0)
    try:
        inv = pd.read_csv(StringIO(investor_csv))
        inv["available_capital"] = pd.to_numeric(inv["available_capital"])
        inv["Can Fund?"] = inv["available_capital"] >= capital_needed
        st.dataframe(inv, use_container_width=True, hide_index=True)
        matches = inv[inv["Can Fund?"]]
        if not matches.empty:
            st.success(f"{len(matches)} investor(s) can fund this deal.")
        else:
            st.warning("No single investor can fully fund this deal. Consider split funding.")
    except Exception:
        st.warning("Use columns: investor,available_capital,target_return,notes")

# -----------------------------
# Settings
# -----------------------------
with tabs[7]:
    st.header("Settings / Integrations")
    st.warning("Live Zillow, PropStream, Buy Box Cartel, Rentometer, email sending, and true AI underwriting require paid APIs or login/API access. This app is structured to plug them in once you have credentials.")
    st.write("""
Included now:
- Full manual underwriting
- Bulk lead ranking from CSV
- CRM tracking in-session
- Portfolio tracking
- LOI generation
- Investment memo generation
- Capital matching

Next integrations to add when you have API access:
1. Persistent database: Supabase or Google Sheets
2. OpenAI API: AI deal memo and listing underwriter
3. Rent source API: RentCast or Rentometer
4. Property data API: PropStream / ATTOM / Zillow-compatible provider
5. Email: Gmail or SendGrid for LOI sending
""")