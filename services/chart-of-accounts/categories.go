package main

var accountCategories = map[AccountType]AccountCategory{
	AccountTypeAsset: {
		Type:          AccountTypeAsset,
		Name:          "Assets",
		Description:   "Resources owned by the bank that have economic value",
		NormalBalance: NormalBalanceDebit,
		CodeRange:     "1000-1999",
		Subcategories: []Subcategory{
			{Code: "1000", Name: "Cash and Cash Equivalents", Description: "Cash on hand, vault cash, ATM cash"},
			{Code: "1100", Name: "Balances with CBN", Description: "Statutory reserves, clearing balances"},
			{Code: "1200", Name: "Balances with Other Banks", Description: "Nostro accounts, interbank placements"},
			{Code: "1300", Name: "Money Market Placements", Description: "Treasury bills, commercial papers"},
			{Code: "1400", Name: "Loans and Advances", Description: "Customer loans, overdrafts, staff loans"},
			{Code: "1500", Name: "Investment Securities", Description: "Government bonds, corporate bonds, equities"},
			{Code: "1600", Name: "Fixed Assets", Description: "Land, buildings, equipment, vehicles"},
			{Code: "1700", Name: "Intangible Assets", Description: "Software, licenses, goodwill"},
			{Code: "1800", Name: "Other Assets", Description: "Prepayments, receivables, deferred tax"},
			{Code: "1900", Name: "Contra Assets", Description: "Accumulated depreciation, loan loss provisions"},
		},
	},
	AccountTypeLiability: {
		Type:          AccountTypeLiability,
		Name:          "Liabilities",
		Description:   "Obligations owed by the bank to external parties",
		NormalBalance: NormalBalanceCredit,
		CodeRange:     "2000-2999",
		Subcategories: []Subcategory{
			{Code: "2000", Name: "Customer Deposits - Demand", Description: "Current accounts, savings accounts"},
			{Code: "2100", Name: "Customer Deposits - Term", Description: "Fixed deposits, call deposits"},
			{Code: "2200", Name: "Balances Due to Banks", Description: "Interbank borrowings, vostro accounts"},
			{Code: "2300", Name: "Money Market Borrowings", Description: "Repos, CBN facilities"},
			{Code: "2400", Name: "Long-term Borrowings", Description: "Bonds issued, subordinated debt"},
			{Code: "2500", Name: "Accrued Interest Payable", Description: "Interest payable on deposits and borrowings"},
			{Code: "2600", Name: "Other Liabilities", Description: "Accounts payable, accrued expenses"},
			{Code: "2700", Name: "Provisions", Description: "Loan loss provisions, contingent liabilities"},
			{Code: "2800", Name: "Deferred Tax Liabilities", Description: "Tax timing differences"},
			{Code: "2900", Name: "Escrow and Trust Accounts", Description: "Customer escrow, trust funds"},
		},
	},
	AccountTypeEquity: {
		Type:          AccountTypeEquity,
		Name:          "Equity",
		Description:   "Residual interest in assets after deducting liabilities",
		NormalBalance: NormalBalanceCredit,
		CodeRange:     "3000-3999",
		Subcategories: []Subcategory{
			{Code: "3000", Name: "Share Capital", Description: "Ordinary shares, preference shares"},
			{Code: "3100", Name: "Share Premium", Description: "Excess over par value"},
			{Code: "3200", Name: "Statutory Reserves", Description: "CBN mandated reserves"},
			{Code: "3300", Name: "General Reserves", Description: "Retained earnings appropriated"},
			{Code: "3400", Name: "Revaluation Reserves", Description: "Asset revaluation surplus"},
			{Code: "3500", Name: "Foreign Currency Translation Reserve", Description: "FX translation differences"},
			{Code: "3600", Name: "Retained Earnings", Description: "Accumulated profits/losses"},
			{Code: "3700", Name: "Current Year Profit/Loss", Description: "Year-to-date net income"},
			{Code: "3800", Name: "Minority Interest", Description: "Non-controlling interest"},
			{Code: "3900", Name: "Other Comprehensive Income", Description: "Fair value changes, hedging reserves"},
		},
	},
	AccountTypeRevenue: {
		Type:          AccountTypeRevenue,
		Name:          "Revenue",
		Description:   "Income earned from banking operations",
		NormalBalance: NormalBalanceCredit,
		CodeRange:     "4000-4999",
		Subcategories: []Subcategory{
			{Code: "4000", Name: "Interest Income - Loans", Description: "Interest on customer loans"},
			{Code: "4100", Name: "Interest Income - Placements", Description: "Interest on interbank placements"},
			{Code: "4200", Name: "Interest Income - Securities", Description: "Interest on investment securities"},
			{Code: "4300", Name: "Fee and Commission Income", Description: "Account fees, transaction fees"},
			{Code: "4400", Name: "Foreign Exchange Income", Description: "FX trading gains, revaluation gains"},
			{Code: "4500", Name: "Trading Income", Description: "Securities trading gains"},
			{Code: "4600", Name: "Dividend Income", Description: "Dividends from investments"},
			{Code: "4700", Name: "Other Operating Income", Description: "Rental income, recoveries"},
			{Code: "4800", Name: "Non-Operating Income", Description: "Gain on asset disposal"},
			{Code: "4900", Name: "Extraordinary Income", Description: "One-time gains"},
		},
	},
	AccountTypeExpense: {
		Type:          AccountTypeExpense,
		Name:          "Expenses",
		Description:   "Costs incurred in banking operations",
		NormalBalance: NormalBalanceDebit,
		CodeRange:     "5000-5999",
		Subcategories: []Subcategory{
			{Code: "5000", Name: "Interest Expense - Deposits", Description: "Interest on customer deposits"},
			{Code: "5100", Name: "Interest Expense - Borrowings", Description: "Interest on interbank borrowings"},
			{Code: "5200", Name: "Fee and Commission Expense", Description: "Correspondent bank fees"},
			{Code: "5300", Name: "Staff Costs", Description: "Salaries, benefits, training"},
			{Code: "5400", Name: "Occupancy Costs", Description: "Rent, utilities, maintenance"},
			{Code: "5500", Name: "Technology Costs", Description: "IT infrastructure, software licenses"},
			{Code: "5600", Name: "Depreciation and Amortization", Description: "Asset depreciation"},
			{Code: "5700", Name: "Loan Loss Provisions", Description: "Credit impairment charges"},
			{Code: "5800", Name: "Other Operating Expenses", Description: "Marketing, professional fees"},
			{Code: "5900", Name: "Tax Expense", Description: "Corporate income tax, VAT"},
		},
	},
}

func GetAccountCategories() map[AccountType]AccountCategory {
	return accountCategories
}

func GetAccountCategory(accountType AccountType) (AccountCategory, bool) {
	category, exists := accountCategories[accountType]
	return category, exists
}

func GetNormalBalance(accountType AccountType) NormalBalance {
	category, exists := accountCategories[accountType]
	if !exists {
		return NormalBalanceDebit
	}
	return category.NormalBalance
}

var cbnAccountMapping = []CBNAccountMapping{
	{CBNCode: "A1", CBNName: "Cash and Balances with Central Bank", CoACode: "1000,1100", ReturnType: "SFP", LineNumber: "1"},
	{CBNCode: "A2", CBNName: "Due from Banks", CoACode: "1200", ReturnType: "SFP", LineNumber: "2"},
	{CBNCode: "A3", CBNName: "Financial Assets Held for Trading", CoACode: "1300", ReturnType: "SFP", LineNumber: "3"},
	{CBNCode: "A4", CBNName: "Derivative Financial Instruments", CoACode: "1310", ReturnType: "SFP", LineNumber: "4"},
	{CBNCode: "A5", CBNName: "Loans and Advances to Customers", CoACode: "1400", ReturnType: "SFP", LineNumber: "5"},
	{CBNCode: "A6", CBNName: "Investment Securities", CoACode: "1500", ReturnType: "SFP", LineNumber: "6"},
	{CBNCode: "A7", CBNName: "Property and Equipment", CoACode: "1600", ReturnType: "SFP", LineNumber: "7"},
	{CBNCode: "A8", CBNName: "Intangible Assets", CoACode: "1700", ReturnType: "SFP", LineNumber: "8"},
	{CBNCode: "A9", CBNName: "Deferred Tax Assets", CoACode: "1810", ReturnType: "SFP", LineNumber: "9"},
	{CBNCode: "A10", CBNName: "Other Assets", CoACode: "1800", ReturnType: "SFP", LineNumber: "10"},

	{CBNCode: "L1", CBNName: "Deposits from Banks", CoACode: "2200", ReturnType: "SFP", LineNumber: "11"},
	{CBNCode: "L2", CBNName: "Deposits from Customers", CoACode: "2000,2100", ReturnType: "SFP", LineNumber: "12"},
	{CBNCode: "L3", CBNName: "Derivative Financial Instruments", CoACode: "2310", ReturnType: "SFP", LineNumber: "13"},
	{CBNCode: "L4", CBNName: "Borrowings", CoACode: "2300,2400", ReturnType: "SFP", LineNumber: "14"},
	{CBNCode: "L5", CBNName: "Current Tax Liabilities", CoACode: "2610", ReturnType: "SFP", LineNumber: "15"},
	{CBNCode: "L6", CBNName: "Deferred Tax Liabilities", CoACode: "2800", ReturnType: "SFP", LineNumber: "16"},
	{CBNCode: "L7", CBNName: "Other Liabilities", CoACode: "2600", ReturnType: "SFP", LineNumber: "17"},
	{CBNCode: "L8", CBNName: "Provisions", CoACode: "2700", ReturnType: "SFP", LineNumber: "18"},

	{CBNCode: "E1", CBNName: "Share Capital", CoACode: "3000", ReturnType: "SFP", LineNumber: "19"},
	{CBNCode: "E2", CBNName: "Share Premium", CoACode: "3100", ReturnType: "SFP", LineNumber: "20"},
	{CBNCode: "E3", CBNName: "Retained Earnings", CoACode: "3600", ReturnType: "SFP", LineNumber: "21"},
	{CBNCode: "E4", CBNName: "Other Reserves", CoACode: "3200,3300,3400,3500,3900", ReturnType: "SFP", LineNumber: "22"},

	{CBNCode: "I1", CBNName: "Interest Income", CoACode: "4000,4100,4200", ReturnType: "PL", LineNumber: "1"},
	{CBNCode: "I2", CBNName: "Interest Expense", CoACode: "5000,5100", ReturnType: "PL", LineNumber: "2"},
	{CBNCode: "I3", CBNName: "Net Interest Income", CoACode: "", ReturnType: "PL", LineNumber: "3"},
	{CBNCode: "I4", CBNName: "Fee and Commission Income", CoACode: "4300", ReturnType: "PL", LineNumber: "4"},
	{CBNCode: "I5", CBNName: "Fee and Commission Expense", CoACode: "5200", ReturnType: "PL", LineNumber: "5"},
	{CBNCode: "I6", CBNName: "Net Trading Income", CoACode: "4400,4500", ReturnType: "PL", LineNumber: "6"},
	{CBNCode: "I7", CBNName: "Other Operating Income", CoACode: "4600,4700", ReturnType: "PL", LineNumber: "7"},
	{CBNCode: "I8", CBNName: "Personnel Expenses", CoACode: "5300", ReturnType: "PL", LineNumber: "8"},
	{CBNCode: "I9", CBNName: "Depreciation and Amortization", CoACode: "5600", ReturnType: "PL", LineNumber: "9"},
	{CBNCode: "I10", CBNName: "Other Operating Expenses", CoACode: "5400,5500,5800", ReturnType: "PL", LineNumber: "10"},
	{CBNCode: "I11", CBNName: "Impairment Charge", CoACode: "5700", ReturnType: "PL", LineNumber: "11"},
	{CBNCode: "I12", CBNName: "Profit Before Tax", CoACode: "", ReturnType: "PL", LineNumber: "12"},
	{CBNCode: "I13", CBNName: "Income Tax Expense", CoACode: "5900", ReturnType: "PL", LineNumber: "13"},
	{CBNCode: "I14", CBNName: "Profit After Tax", CoACode: "", ReturnType: "PL", LineNumber: "14"},

	{CBNCode: "CAR1", CBNName: "Tier 1 Capital", CoACode: "3000,3100,3600", ReturnType: "CAR", LineNumber: "1"},
	{CBNCode: "CAR2", CBNName: "Tier 2 Capital", CoACode: "3200,3300,2400", ReturnType: "CAR", LineNumber: "2"},
	{CBNCode: "CAR3", CBNName: "Total Qualifying Capital", CoACode: "", ReturnType: "CAR", LineNumber: "3"},
	{CBNCode: "CAR4", CBNName: "Risk Weighted Assets", CoACode: "", ReturnType: "CAR", LineNumber: "4"},
	{CBNCode: "CAR5", CBNName: "Capital Adequacy Ratio", CoACode: "", ReturnType: "CAR", LineNumber: "5"},

	{CBNCode: "LR1", CBNName: "Total Liquid Assets", CoACode: "1000,1100,1200,1300", ReturnType: "LR", LineNumber: "1"},
	{CBNCode: "LR2", CBNName: "Total Deposit Liabilities", CoACode: "2000,2100", ReturnType: "LR", LineNumber: "2"},
	{CBNCode: "LR3", CBNName: "Liquidity Ratio", CoACode: "", ReturnType: "LR", LineNumber: "3"},
}

func GetCBNAccountMapping() []CBNAccountMapping {
	return cbnAccountMapping
}

func GetCBNMappingByReturnType(returnType string) []CBNAccountMapping {
	var filtered []CBNAccountMapping
	for _, mapping := range cbnAccountMapping {
		if mapping.ReturnType == returnType {
			filtered = append(filtered, mapping)
		}
	}
	return filtered
}

var defaultAccounts = []CreateAccountRequest{
	{Code: "1000", Name: "Cash on Hand", Type: AccountTypeAsset, Description: "Physical cash in vaults and tills"},
	{Code: "1010", Name: "Vault Cash - Head Office", Type: AccountTypeAsset, ParentID: "1000"},
	{Code: "1020", Name: "Vault Cash - Branches", Type: AccountTypeAsset, ParentID: "1000"},
	{Code: "1030", Name: "ATM Cash", Type: AccountTypeAsset, ParentID: "1000"},
	{Code: "1040", Name: "Cash in Transit", Type: AccountTypeAsset, ParentID: "1000"},

	{Code: "1100", Name: "Balances with Central Bank of Nigeria", Type: AccountTypeAsset, Description: "CBN statutory and clearing balances"},
	{Code: "1110", Name: "CBN Statutory Reserve", Type: AccountTypeAsset, ParentID: "1100", CBNCode: "A1"},
	{Code: "1120", Name: "CBN Clearing Account", Type: AccountTypeAsset, ParentID: "1100", CBNCode: "A1"},
	{Code: "1130", Name: "CBN Standing Deposit Facility", Type: AccountTypeAsset, ParentID: "1100", CBNCode: "A1"},

	{Code: "1200", Name: "Balances with Other Banks", Type: AccountTypeAsset, Description: "Nostro accounts and interbank placements", CBNCode: "A2"},
	{Code: "1210", Name: "Nostro Accounts - NGN", Type: AccountTypeAsset, ParentID: "1200"},
	{Code: "1220", Name: "Nostro Accounts - USD", Type: AccountTypeAsset, ParentID: "1200", Currency: "USD"},
	{Code: "1230", Name: "Nostro Accounts - GBP", Type: AccountTypeAsset, ParentID: "1200", Currency: "GBP"},
	{Code: "1240", Name: "Nostro Accounts - EUR", Type: AccountTypeAsset, ParentID: "1200", Currency: "EUR"},
	{Code: "1250", Name: "Interbank Placements", Type: AccountTypeAsset, ParentID: "1200"},

	{Code: "1300", Name: "Money Market Instruments", Type: AccountTypeAsset, Description: "Short-term investments", CBNCode: "A3"},
	{Code: "1310", Name: "Treasury Bills", Type: AccountTypeAsset, ParentID: "1300"},
	{Code: "1320", Name: "Commercial Papers", Type: AccountTypeAsset, ParentID: "1300"},
	{Code: "1330", Name: "Bankers Acceptances", Type: AccountTypeAsset, ParentID: "1300"},

	{Code: "1400", Name: "Loans and Advances", Type: AccountTypeAsset, Description: "Customer credit facilities", CBNCode: "A5"},
	{Code: "1410", Name: "Consumer Loans", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1411", Name: "Personal Loans", Type: AccountTypeAsset, ParentID: "1410"},
	{Code: "1412", Name: "Auto Loans", Type: AccountTypeAsset, ParentID: "1410"},
	{Code: "1413", Name: "Education Loans", Type: AccountTypeAsset, ParentID: "1410"},
	{Code: "1420", Name: "Mortgage Loans", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1421", Name: "Residential Mortgages", Type: AccountTypeAsset, ParentID: "1420"},
	{Code: "1422", Name: "Commercial Mortgages", Type: AccountTypeAsset, ParentID: "1420"},
	{Code: "1423", Name: "NHF Mortgages", Type: AccountTypeAsset, ParentID: "1420"},
	{Code: "1430", Name: "SME Loans", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1440", Name: "Corporate Loans", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1450", Name: "Agricultural Loans", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1451", Name: "Crop Financing", Type: AccountTypeAsset, ParentID: "1450"},
	{Code: "1452", Name: "Livestock Financing", Type: AccountTypeAsset, ParentID: "1450"},
	{Code: "1453", Name: "Agri-Input Financing", Type: AccountTypeAsset, ParentID: "1450"},
	{Code: "1460", Name: "Overdrafts", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1470", Name: "Staff Loans", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1480", Name: "Trade Finance", Type: AccountTypeAsset, ParentID: "1400"},
	{Code: "1481", Name: "Letters of Credit", Type: AccountTypeAsset, ParentID: "1480"},
	{Code: "1482", Name: "Bank Guarantees", Type: AccountTypeAsset, ParentID: "1480"},
	{Code: "1490", Name: "Accrued Interest Receivable", Type: AccountTypeAsset, ParentID: "1400"},

	{Code: "1500", Name: "Investment Securities", Type: AccountTypeAsset, Description: "Long-term investments", CBNCode: "A6"},
	{Code: "1510", Name: "FGN Bonds", Type: AccountTypeAsset, ParentID: "1500"},
	{Code: "1520", Name: "State Government Bonds", Type: AccountTypeAsset, ParentID: "1500"},
	{Code: "1530", Name: "Corporate Bonds", Type: AccountTypeAsset, ParentID: "1500"},
	{Code: "1540", Name: "Equity Investments", Type: AccountTypeAsset, ParentID: "1500"},
	{Code: "1550", Name: "Investment in Subsidiaries", Type: AccountTypeAsset, ParentID: "1500"},

	{Code: "1600", Name: "Property and Equipment", Type: AccountTypeAsset, Description: "Fixed assets", CBNCode: "A7"},
	{Code: "1610", Name: "Land", Type: AccountTypeAsset, ParentID: "1600"},
	{Code: "1620", Name: "Buildings", Type: AccountTypeAsset, ParentID: "1600"},
	{Code: "1630", Name: "Furniture and Fittings", Type: AccountTypeAsset, ParentID: "1600"},
	{Code: "1640", Name: "Computer Equipment", Type: AccountTypeAsset, ParentID: "1600"},
	{Code: "1650", Name: "Motor Vehicles", Type: AccountTypeAsset, ParentID: "1600"},
	{Code: "1660", Name: "ATM Machines", Type: AccountTypeAsset, ParentID: "1600"},
	{Code: "1670", Name: "Leasehold Improvements", Type: AccountTypeAsset, ParentID: "1600"},

	{Code: "1700", Name: "Intangible Assets", Type: AccountTypeAsset, Description: "Non-physical assets", CBNCode: "A8"},
	{Code: "1710", Name: "Core Banking Software", Type: AccountTypeAsset, ParentID: "1700"},
	{Code: "1720", Name: "Other Software Licenses", Type: AccountTypeAsset, ParentID: "1700"},
	{Code: "1730", Name: "Goodwill", Type: AccountTypeAsset, ParentID: "1700"},

	{Code: "1800", Name: "Other Assets", Type: AccountTypeAsset, Description: "Miscellaneous assets", CBNCode: "A10"},
	{Code: "1810", Name: "Deferred Tax Assets", Type: AccountTypeAsset, ParentID: "1800", CBNCode: "A9"},
	{Code: "1820", Name: "Prepaid Expenses", Type: AccountTypeAsset, ParentID: "1800"},
	{Code: "1830", Name: "Accounts Receivable", Type: AccountTypeAsset, ParentID: "1800"},
	{Code: "1840", Name: "Clearing Items", Type: AccountTypeAsset, ParentID: "1800"},

	{Code: "1900", Name: "Contra Asset Accounts", Type: AccountTypeAsset, Description: "Asset reductions"},
	{Code: "1910", Name: "Accumulated Depreciation - Buildings", Type: AccountTypeAsset, ParentID: "1900"},
	{Code: "1920", Name: "Accumulated Depreciation - Equipment", Type: AccountTypeAsset, ParentID: "1900"},
	{Code: "1930", Name: "Accumulated Depreciation - Vehicles", Type: AccountTypeAsset, ParentID: "1900"},
	{Code: "1940", Name: "Accumulated Amortization - Software", Type: AccountTypeAsset, ParentID: "1900"},
	{Code: "1950", Name: "Loan Loss Provision - Specific", Type: AccountTypeAsset, ParentID: "1900"},
	{Code: "1960", Name: "Loan Loss Provision - General", Type: AccountTypeAsset, ParentID: "1900"},

	{Code: "2000", Name: "Customer Deposits - Demand", Type: AccountTypeLiability, Description: "Current and savings accounts", CBNCode: "L2"},
	{Code: "2010", Name: "Current Accounts - Individual", Type: AccountTypeLiability, ParentID: "2000"},
	{Code: "2020", Name: "Current Accounts - Corporate", Type: AccountTypeLiability, ParentID: "2000"},
	{Code: "2030", Name: "Savings Accounts", Type: AccountTypeLiability, ParentID: "2000"},
	{Code: "2040", Name: "Domiciliary Accounts - USD", Type: AccountTypeLiability, ParentID: "2000", Currency: "USD"},
	{Code: "2050", Name: "Domiciliary Accounts - GBP", Type: AccountTypeLiability, ParentID: "2000", Currency: "GBP"},
	{Code: "2060", Name: "Domiciliary Accounts - EUR", Type: AccountTypeLiability, ParentID: "2000", Currency: "EUR"},
	{Code: "2070", Name: "Esusu/Ajo Accounts", Type: AccountTypeLiability, ParentID: "2000"},
	{Code: "2080", Name: "Digital Wallet Accounts", Type: AccountTypeLiability, ParentID: "2000"},

	{Code: "2100", Name: "Customer Deposits - Term", Type: AccountTypeLiability, Description: "Fixed and call deposits", CBNCode: "L2"},
	{Code: "2110", Name: "Fixed Deposits - 30 Days", Type: AccountTypeLiability, ParentID: "2100"},
	{Code: "2120", Name: "Fixed Deposits - 60 Days", Type: AccountTypeLiability, ParentID: "2100"},
	{Code: "2130", Name: "Fixed Deposits - 90 Days", Type: AccountTypeLiability, ParentID: "2100"},
	{Code: "2140", Name: "Fixed Deposits - 180 Days", Type: AccountTypeLiability, ParentID: "2100"},
	{Code: "2150", Name: "Fixed Deposits - 365 Days", Type: AccountTypeLiability, ParentID: "2100"},
	{Code: "2160", Name: "Call Deposits", Type: AccountTypeLiability, ParentID: "2100"},

	{Code: "2200", Name: "Due to Banks", Type: AccountTypeLiability, Description: "Interbank borrowings", CBNCode: "L1"},
	{Code: "2210", Name: "Vostro Accounts", Type: AccountTypeLiability, ParentID: "2200"},
	{Code: "2220", Name: "Interbank Takings", Type: AccountTypeLiability, ParentID: "2200"},
	{Code: "2230", Name: "Money Market Borrowings", Type: AccountTypeLiability, ParentID: "2200"},

	{Code: "2300", Name: "CBN Facilities", Type: AccountTypeLiability, Description: "Central bank borrowings", CBNCode: "L4"},
	{Code: "2310", Name: "Standing Lending Facility", Type: AccountTypeLiability, ParentID: "2300"},
	{Code: "2320", Name: "Repo Borrowings", Type: AccountTypeLiability, ParentID: "2300"},

	{Code: "2400", Name: "Long-term Borrowings", Type: AccountTypeLiability, Description: "Bonds and subordinated debt", CBNCode: "L4"},
	{Code: "2410", Name: "Senior Bonds", Type: AccountTypeLiability, ParentID: "2400"},
	{Code: "2420", Name: "Subordinated Debt", Type: AccountTypeLiability, ParentID: "2400"},
	{Code: "2430", Name: "Development Finance Loans", Type: AccountTypeLiability, ParentID: "2400"},

	{Code: "2500", Name: "Accrued Interest Payable", Type: AccountTypeLiability, Description: "Interest payable on deposits"},
	{Code: "2510", Name: "Interest Payable - Savings", Type: AccountTypeLiability, ParentID: "2500"},
	{Code: "2520", Name: "Interest Payable - Fixed Deposits", Type: AccountTypeLiability, ParentID: "2500"},
	{Code: "2530", Name: "Interest Payable - Borrowings", Type: AccountTypeLiability, ParentID: "2500"},

	{Code: "2600", Name: "Other Liabilities", Type: AccountTypeLiability, Description: "Miscellaneous liabilities", CBNCode: "L7"},
	{Code: "2610", Name: "Current Tax Payable", Type: AccountTypeLiability, ParentID: "2600", CBNCode: "L5"},
	{Code: "2620", Name: "Accounts Payable", Type: AccountTypeLiability, ParentID: "2600"},
	{Code: "2630", Name: "Accrued Expenses", Type: AccountTypeLiability, ParentID: "2600"},
	{Code: "2640", Name: "Unearned Income", Type: AccountTypeLiability, ParentID: "2600"},
	{Code: "2650", Name: "Dividends Payable", Type: AccountTypeLiability, ParentID: "2600"},
	{Code: "2660", Name: "Clearing Items", Type: AccountTypeLiability, ParentID: "2600"},

	{Code: "2700", Name: "Provisions", Type: AccountTypeLiability, Description: "Contingent liabilities", CBNCode: "L8"},
	{Code: "2710", Name: "Provision for Loan Losses", Type: AccountTypeLiability, ParentID: "2700"},
	{Code: "2720", Name: "Provision for Litigation", Type: AccountTypeLiability, ParentID: "2700"},
	{Code: "2730", Name: "Provision for Staff Benefits", Type: AccountTypeLiability, ParentID: "2700"},

	{Code: "2800", Name: "Deferred Tax Liabilities", Type: AccountTypeLiability, Description: "Tax timing differences", CBNCode: "L6"},

	{Code: "2900", Name: "Escrow and Trust Accounts", Type: AccountTypeLiability, Description: "Fiduciary accounts"},
	{Code: "2910", Name: "Customer Escrow Accounts", Type: AccountTypeLiability, ParentID: "2900"},
	{Code: "2920", Name: "Mortgage Escrow", Type: AccountTypeLiability, ParentID: "2900"},
	{Code: "2930", Name: "Trade Escrow", Type: AccountTypeLiability, ParentID: "2900"},

	{Code: "3000", Name: "Share Capital", Type: AccountTypeEquity, Description: "Issued share capital", CBNCode: "E1"},
	{Code: "3010", Name: "Ordinary Shares", Type: AccountTypeEquity, ParentID: "3000"},
	{Code: "3020", Name: "Preference Shares", Type: AccountTypeEquity, ParentID: "3000"},

	{Code: "3100", Name: "Share Premium", Type: AccountTypeEquity, Description: "Excess over par value", CBNCode: "E2"},

	{Code: "3200", Name: "Statutory Reserves", Type: AccountTypeEquity, Description: "CBN mandated reserves", CBNCode: "E4"},
	{Code: "3210", Name: "Statutory Reserve Fund", Type: AccountTypeEquity, ParentID: "3200"},
	{Code: "3220", Name: "Small Scale Industries Reserve", Type: AccountTypeEquity, ParentID: "3200"},

	{Code: "3300", Name: "General Reserves", Type: AccountTypeEquity, Description: "Appropriated retained earnings", CBNCode: "E4"},

	{Code: "3400", Name: "Revaluation Reserves", Type: AccountTypeEquity, Description: "Asset revaluation surplus", CBNCode: "E4"},
	{Code: "3410", Name: "Property Revaluation Reserve", Type: AccountTypeEquity, ParentID: "3400"},
	{Code: "3420", Name: "Investment Revaluation Reserve", Type: AccountTypeEquity, ParentID: "3400"},

	{Code: "3500", Name: "Foreign Currency Translation Reserve", Type: AccountTypeEquity, Description: "FX translation differences", CBNCode: "E4"},

	{Code: "3600", Name: "Retained Earnings", Type: AccountTypeEquity, Description: "Accumulated profits/losses", CBNCode: "E3"},

	{Code: "3700", Name: "Current Year Profit/Loss", Type: AccountTypeEquity, Description: "Year-to-date net income"},

	{Code: "4000", Name: "Interest Income - Loans", Type: AccountTypeRevenue, Description: "Interest on customer loans", CBNCode: "I1"},
	{Code: "4010", Name: "Interest - Consumer Loans", Type: AccountTypeRevenue, ParentID: "4000"},
	{Code: "4020", Name: "Interest - Mortgage Loans", Type: AccountTypeRevenue, ParentID: "4000"},
	{Code: "4030", Name: "Interest - SME Loans", Type: AccountTypeRevenue, ParentID: "4000"},
	{Code: "4040", Name: "Interest - Corporate Loans", Type: AccountTypeRevenue, ParentID: "4000"},
	{Code: "4050", Name: "Interest - Agricultural Loans", Type: AccountTypeRevenue, ParentID: "4000"},
	{Code: "4060", Name: "Interest - Overdrafts", Type: AccountTypeRevenue, ParentID: "4000"},
	{Code: "4070", Name: "Interest - Trade Finance", Type: AccountTypeRevenue, ParentID: "4000"},

	{Code: "4100", Name: "Interest Income - Placements", Type: AccountTypeRevenue, Description: "Interest on interbank placements", CBNCode: "I1"},
	{Code: "4110", Name: "Interest - Interbank Placements", Type: AccountTypeRevenue, ParentID: "4100"},
	{Code: "4120", Name: "Interest - CBN Placements", Type: AccountTypeRevenue, ParentID: "4100"},

	{Code: "4200", Name: "Interest Income - Securities", Type: AccountTypeRevenue, Description: "Interest on investment securities", CBNCode: "I1"},
	{Code: "4210", Name: "Interest - Treasury Bills", Type: AccountTypeRevenue, ParentID: "4200"},
	{Code: "4220", Name: "Interest - FGN Bonds", Type: AccountTypeRevenue, ParentID: "4200"},
	{Code: "4230", Name: "Interest - Corporate Bonds", Type: AccountTypeRevenue, ParentID: "4200"},

	{Code: "4300", Name: "Fee and Commission Income", Type: AccountTypeRevenue, Description: "Non-interest income", CBNCode: "I4"},
	{Code: "4310", Name: "Account Maintenance Fees", Type: AccountTypeRevenue, ParentID: "4300"},
	{Code: "4320", Name: "Transaction Fees", Type: AccountTypeRevenue, ParentID: "4300"},
	{Code: "4330", Name: "Card Fees", Type: AccountTypeRevenue, ParentID: "4300"},
	{Code: "4340", Name: "Loan Processing Fees", Type: AccountTypeRevenue, ParentID: "4300"},
	{Code: "4350", Name: "Trade Finance Fees", Type: AccountTypeRevenue, ParentID: "4300"},
	{Code: "4360", Name: "Commission on Turnover", Type: AccountTypeRevenue, ParentID: "4300"},
	{Code: "4370", Name: "API/Platform Fees", Type: AccountTypeRevenue, ParentID: "4300"},

	{Code: "4400", Name: "Foreign Exchange Income", Type: AccountTypeRevenue, Description: "FX trading gains", CBNCode: "I6"},
	{Code: "4410", Name: "FX Trading Gains", Type: AccountTypeRevenue, ParentID: "4400"},
	{Code: "4420", Name: "FX Revaluation Gains", Type: AccountTypeRevenue, ParentID: "4400"},

	{Code: "4500", Name: "Trading Income", Type: AccountTypeRevenue, Description: "Securities trading gains", CBNCode: "I6"},

	{Code: "4600", Name: "Dividend Income", Type: AccountTypeRevenue, Description: "Dividends from investments", CBNCode: "I7"},

	{Code: "4700", Name: "Other Operating Income", Type: AccountTypeRevenue, Description: "Miscellaneous income", CBNCode: "I7"},
	{Code: "4710", Name: "Rental Income", Type: AccountTypeRevenue, ParentID: "4700"},
	{Code: "4720", Name: "Recoveries", Type: AccountTypeRevenue, ParentID: "4700"},
	{Code: "4730", Name: "Insurance Commission", Type: AccountTypeRevenue, ParentID: "4700"},

	{Code: "5000", Name: "Interest Expense - Deposits", Type: AccountTypeExpense, Description: "Interest on customer deposits", CBNCode: "I2"},
	{Code: "5010", Name: "Interest - Savings Accounts", Type: AccountTypeExpense, ParentID: "5000"},
	{Code: "5020", Name: "Interest - Fixed Deposits", Type: AccountTypeExpense, ParentID: "5000"},
	{Code: "5030", Name: "Interest - Domiciliary Accounts", Type: AccountTypeExpense, ParentID: "5000"},

	{Code: "5100", Name: "Interest Expense - Borrowings", Type: AccountTypeExpense, Description: "Interest on borrowings", CBNCode: "I2"},
	{Code: "5110", Name: "Interest - Interbank Borrowings", Type: AccountTypeExpense, ParentID: "5100"},
	{Code: "5120", Name: "Interest - CBN Facilities", Type: AccountTypeExpense, ParentID: "5100"},
	{Code: "5130", Name: "Interest - Bonds", Type: AccountTypeExpense, ParentID: "5100"},

	{Code: "5200", Name: "Fee and Commission Expense", Type: AccountTypeExpense, Description: "Fees paid to others", CBNCode: "I5"},
	{Code: "5210", Name: "Correspondent Bank Fees", Type: AccountTypeExpense, ParentID: "5200"},
	{Code: "5220", Name: "NIBSS Fees", Type: AccountTypeExpense, ParentID: "5200"},
	{Code: "5230", Name: "Card Scheme Fees", Type: AccountTypeExpense, ParentID: "5200"},

	{Code: "5300", Name: "Staff Costs", Type: AccountTypeExpense, Description: "Personnel expenses", CBNCode: "I8"},
	{Code: "5310", Name: "Salaries and Wages", Type: AccountTypeExpense, ParentID: "5300"},
	{Code: "5320", Name: "Pension Contributions", Type: AccountTypeExpense, ParentID: "5300"},
	{Code: "5330", Name: "Medical Benefits", Type: AccountTypeExpense, ParentID: "5300"},
	{Code: "5340", Name: "Training and Development", Type: AccountTypeExpense, ParentID: "5300"},
	{Code: "5350", Name: "Staff Welfare", Type: AccountTypeExpense, ParentID: "5300"},

	{Code: "5400", Name: "Occupancy Costs", Type: AccountTypeExpense, Description: "Premises expenses", CBNCode: "I10"},
	{Code: "5410", Name: "Rent", Type: AccountTypeExpense, ParentID: "5400"},
	{Code: "5420", Name: "Utilities", Type: AccountTypeExpense, ParentID: "5400"},
	{Code: "5430", Name: "Repairs and Maintenance", Type: AccountTypeExpense, ParentID: "5400"},
	{Code: "5440", Name: "Security", Type: AccountTypeExpense, ParentID: "5400"},

	{Code: "5500", Name: "Technology Costs", Type: AccountTypeExpense, Description: "IT expenses", CBNCode: "I10"},
	{Code: "5510", Name: "Software Licenses", Type: AccountTypeExpense, ParentID: "5500"},
	{Code: "5520", Name: "Hardware Maintenance", Type: AccountTypeExpense, ParentID: "5500"},
	{Code: "5530", Name: "Telecommunications", Type: AccountTypeExpense, ParentID: "5500"},
	{Code: "5540", Name: "Cloud Services", Type: AccountTypeExpense, ParentID: "5500"},
	{Code: "5550", Name: "Cybersecurity", Type: AccountTypeExpense, ParentID: "5500"},

	{Code: "5600", Name: "Depreciation and Amortization", Type: AccountTypeExpense, Description: "Asset depreciation", CBNCode: "I9"},
	{Code: "5610", Name: "Depreciation - Buildings", Type: AccountTypeExpense, ParentID: "5600"},
	{Code: "5620", Name: "Depreciation - Equipment", Type: AccountTypeExpense, ParentID: "5600"},
	{Code: "5630", Name: "Depreciation - Vehicles", Type: AccountTypeExpense, ParentID: "5600"},
	{Code: "5640", Name: "Amortization - Software", Type: AccountTypeExpense, ParentID: "5600"},

	{Code: "5700", Name: "Loan Loss Provisions", Type: AccountTypeExpense, Description: "Credit impairment charges", CBNCode: "I11"},
	{Code: "5710", Name: "Specific Provisions", Type: AccountTypeExpense, ParentID: "5700"},
	{Code: "5720", Name: "General Provisions", Type: AccountTypeExpense, ParentID: "5700"},
	{Code: "5730", Name: "Write-offs", Type: AccountTypeExpense, ParentID: "5700"},

	{Code: "5800", Name: "Other Operating Expenses", Type: AccountTypeExpense, Description: "Miscellaneous expenses", CBNCode: "I10"},
	{Code: "5810", Name: "Marketing and Advertising", Type: AccountTypeExpense, ParentID: "5800"},
	{Code: "5820", Name: "Professional Fees", Type: AccountTypeExpense, ParentID: "5800"},
	{Code: "5830", Name: "Audit Fees", Type: AccountTypeExpense, ParentID: "5800"},
	{Code: "5840", Name: "Legal Fees", Type: AccountTypeExpense, ParentID: "5800"},
	{Code: "5850", Name: "Insurance", Type: AccountTypeExpense, ParentID: "5800"},
	{Code: "5860", Name: "Travel and Entertainment", Type: AccountTypeExpense, ParentID: "5800"},
	{Code: "5870", Name: "Stationery and Supplies", Type: AccountTypeExpense, ParentID: "5800"},
	{Code: "5880", Name: "Regulatory Fees", Type: AccountTypeExpense, ParentID: "5800"},

	{Code: "5900", Name: "Tax Expense", Type: AccountTypeExpense, Description: "Corporate taxes", CBNCode: "I13"},
	{Code: "5910", Name: "Corporate Income Tax", Type: AccountTypeExpense, ParentID: "5900"},
	{Code: "5920", Name: "Education Tax", Type: AccountTypeExpense, ParentID: "5900"},
	{Code: "5930", Name: "NITDA Levy", Type: AccountTypeExpense, ParentID: "5900"},
	{Code: "5940", Name: "Police Trust Fund Levy", Type: AccountTypeExpense, ParentID: "5900"},
}

func GetDefaultAccounts() []CreateAccountRequest {
	return defaultAccounts
}
