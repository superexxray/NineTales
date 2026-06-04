"""
category_definitions.py
=======================
Rich semantic descriptions for each financial document category.

Each description is deliberately verbose and covers multiple angles of the
same category so that the sentence-transformer embedding captures the full
semantic space of documents that belong to that category.
"""

# ---------------------------------------------------------------------------
# Each value is a multi-sentence, terminology-rich description of the category.
# More detail → richer embeddings → better cosine-similarity discrimination.
# ---------------------------------------------------------------------------

CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "ALM": (
        "Asset Liability Management (ALM) report focuses on the structural balance sheet risk "
        "of a financial institution, particularly banks, NBFCs, and insurance companies. "
        "It covers interest rate risk, liquidity risk, and gap analysis between rate-sensitive "
        "assets and rate-sensitive liabilities across short-, medium-, and long-term buckets. "
        "Key metrics include the Net Interest Margin (NIM), repricing schedules, duration of assets "
        "and liabilities, Modified Duration of Equity (MDE), and dynamic liquidity statements. "
        "The document often contains time buckets such as 1–7 days, 8–14 days, 15–28 days, "
        "29 days to 3 months, 3–6 months, 6 months to 1 year, 1–3 years, 3–5 years, and over 5 years. "
        "It may also include the Liquidity Coverage Ratio (LCR), Net Stable Funding Ratio (NSFR), "
        "High Quality Liquid Assets (HQLA), stress testing results, cash flow projections, "
        "and RBI or regulator-mandated ALM return formats. "
        "The interest rate sensitivity analysis, basis risk, embedded option risk, and yield curve "
        "risk are frequently discussed sections. ALM committees (ALCO) minutes and decisions may "
        "also be embedded."
    ),

    "Shareholding Pattern": (
        "Shareholding Pattern is a regulatory disclosure mandated by SEBI for listed companies "
        "in India, typically filed as Form SHP on a quarterly basis with stock exchanges. "
        "It details the ownership structure of the company's share capital, broken down into "
        "Promoter and Promoter Group holdings (Indian and foreign promoters), public institutional "
        "investors such as Mutual Funds, Foreign Portfolio Investors (FPIs), Foreign Institutional "
        "Investors (FIIs), Insurance Companies, Banks, Financial Institutions, and non-institutional "
        "public shareholders including High Net-worth Individuals (HNIs), retail shareholders, "
        "NRIs, Bodies Corporate, and Employee Trusts. "
        "The document specifies the total number of shares held, percentage of shareholding, "
        "number of shareholders, pledged shares, encumbered shares, and shares held in dematerialized "
        "form versus physical form. "
        "It distinguishes between fully paid-up equity shares, partly paid-up shares, warrants, "
        "convertible securities, and depository receipts. "
        "Columns typically include Category of Shareholder, No. of Shareholders, Total No. of Shares, "
        "No. of Shares held in Demat form, Total shareholding as a percentage of total number of shares. "
        "It may also contain notes on change in promoter holdings, creeping acquisition disclosures, "
        "and lock-in details."
    ),

    "Borrowing Profile": (
        "Borrowing Profile is a document that provides a comprehensive overview of an entity's "
        "outstanding debt and funding mix. It is commonly prepared by corporates, NBFCs, banks, "
        "and infrastructure companies for investor presentations, credit rating reviews, or "
        "lender reporting. "
        "The document includes details on term loans from banks and financial institutions, "
        "Non-Convertible Debentures (NCDs), Commercial Papers (CPs), External Commercial Borrowings (ECBs), "
        "Subordinated Debt, Tier I and Tier II capital instruments, Working Capital facilities, "
        "Cash Credit (CC) limits, Overdraft (OD) facilities, and Foreign Currency Term Loans (FCTLs). "
        "Key metrics covered are the total debt outstanding, debt maturity profile (bucket-wise "
        "principal repayment schedule), weighted average cost of borrowing (WACB), "
        "average tenor of debt, lender-wise concentration, secured versus unsecured debt split, "
        "fixed versus floating rate mix, Debt-to-Equity ratio, Net Debt, Interest Coverage Ratio (ICR), "
        "Debt Service Coverage Ratio (DSCR), and leverage ratios. "
        "Collateral details, security cover, covenant details, and CRISIL, ICRA, CARE, or Fitch "
        "credit ratings of individual instruments may also be included. "
        "Schedule of repayments, bullet maturities, and refinancing plans are typically discussed."
    ),

    "Annual Report": (
        "Annual Report is a comprehensive statutory document published by a company at the end of "
        "each financial year for its shareholders and regulators. "
        "It contains audited financial statements including the Balance Sheet (Statement of Financial "
        "Position), Profit and Loss Statement (Income Statement / Statement of Comprehensive Income), "
        "Cash Flow Statement (prepared under the indirect or direct method), and the Statement of "
        "Changes in Equity. "
        "Key financial data includes Revenue from Operations, Other Income, Total Income, Cost of "
        "Goods Sold (COGS), Gross Profit, EBITDA, EBIT, Finance Costs, Depreciation and Amortisation "
        "(D&A), PBT, PAT, EPS (Basic and Diluted), DPS, Retained Earnings, and Return on Equity (ROE). "
        "The Balance Sheet covers Fixed Assets, Capital Work-in-Progress (CWIP), Intangible Assets, "
        "Investments, Inventory, Trade Receivables, Cash and Cash Equivalents, Total Assets, "
        "Share Capital, Reserves and Surplus, Long-term Borrowings, Short-term Borrowings, "
        "Trade Payables, and Total Liabilities. "
        "Non-financial sections include the Board of Directors' Report, Management Discussion and "
        "Analysis (MDA), Corporate Governance Report, Auditor's Report (including CARO, Key Audit "
        "Matters), Notes to Financial Statements (disclosures on accounting policies, contingent "
        "liabilities, related party transactions, segment reporting), and the CSR Report. "
        "Annual Reports filed with the Ministry of Corporate Affairs (MCA) under the Companies Act "
        "2013 and for listed entities with SEBI follow prescribed formats such as Schedule III."
    ),

    "Portfolio Performance": (
        "Portfolio Performance report documents the investment returns, risk metrics, and asset "
        "allocation of an investment portfolio, fund, or scheme over a specific time period. "
        "It is commonly prepared by mutual funds, PMS providers, AIFs, insurance companies, "
        "pension funds, sovereign wealth funds, and wealth management firms. "
        "Key performance metrics include Absolute Return, CAGR, XIRR, Annualised Return, "
        "Rolling Returns, SIP returns, benchmark-adjusted returns, Alpha, Beta, Sharpe Ratio, "
        "Sortino Ratio, Treynor Ratio, Information Ratio, Standard Deviation, and Maximum Drawdown. "
        "The document typically shows NAV (Net Asset Value) movement over time, AUM (Assets Under "
        "Management) growth or decline, fund-level and scheme-level performance, sector-wise and "
        "asset-wise allocation as a percentage of the portfolio, top holdings, churn ratio, "
        "expense ratio, and exit load details. "
        "Benchmark comparisons against indices such as Nifty 50, BSE Sensex, Nifty 500, Nifty Midcap, "
        "Bloomberg Barclays Bond Index, or MSCI indices are standard. "
        "Attribution analysis (contribution of individual securities or sectors to overall returns), "
        "dividend declared and reinvested history, and risk-adjusted return comparisons are also common. "
        "Fund manager commentary and market outlook sections are frequently included."
    ),
}

# Ordered list of category names (preserves display order)
CATEGORY_NAMES: list[str] = list(CATEGORY_DESCRIPTIONS.keys())
