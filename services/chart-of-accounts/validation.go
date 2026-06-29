package main

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

type AccountCodeFormat struct {
	Pattern     string
	MinLength   int
	MaxLength   int
	Prefix      string
	Separator   string
	Description string
}

var DefaultAccountCodeFormats = map[AccountType]AccountCodeFormat{
	AccountTypeAsset: {
		Pattern:     `^1\d{3,5}$`,
		MinLength:   4,
		MaxLength:   6,
		Prefix:      "1",
		Description: "Asset accounts start with 1 (e.g., 1000, 10001)",
	},
	AccountTypeLiability: {
		Pattern:     `^2\d{3,5}$`,
		MinLength:   4,
		MaxLength:   6,
		Prefix:      "2",
		Description: "Liability accounts start with 2 (e.g., 2000, 20001)",
	},
	AccountTypeEquity: {
		Pattern:     `^3\d{3,5}$`,
		MinLength:   4,
		MaxLength:   6,
		Prefix:      "3",
		Description: "Equity accounts start with 3 (e.g., 3000, 30001)",
	},
	AccountTypeRevenue: {
		Pattern:     `^4\d{3,5}$`,
		MinLength:   4,
		MaxLength:   6,
		Prefix:      "4",
		Description: "Revenue accounts start with 4 (e.g., 4000, 40001)",
	},
	AccountTypeExpense: {
		Pattern:     `^5\d{3,5}$`,
		MinLength:   4,
		MaxLength:   6,
		Prefix:      "5",
		Description: "Expense accounts start with 5 (e.g., 5000, 50001)",
	},
}

type AccountCodeValidator struct {
	formats map[AccountType]AccountCodeFormat
}

func NewAccountCodeValidator() *AccountCodeValidator {
	return &AccountCodeValidator{
		formats: DefaultAccountCodeFormats,
	}
}

func (v *AccountCodeValidator) SetFormat(accountType AccountType, format AccountCodeFormat) {
	v.formats[accountType] = format
}

func (v *AccountCodeValidator) ValidateCode(code string, accountType AccountType) error {
	if code == "" {
		return errors.New("account code is required")
	}

	code = strings.TrimSpace(code)

	format, exists := v.formats[accountType]
	if !exists {
		return fmt.Errorf("unknown account type: %s", accountType)
	}

	if len(code) < format.MinLength {
		return fmt.Errorf("account code must be at least %d characters", format.MinLength)
	}

	if len(code) > format.MaxLength {
		return fmt.Errorf("account code must be at most %d characters", format.MaxLength)
	}

	if format.Prefix != "" && !strings.HasPrefix(code, format.Prefix) {
		return fmt.Errorf("account code for %s must start with '%s'", accountType, format.Prefix)
	}

	if format.Pattern != "" {
		matched, err := regexp.MatchString(format.Pattern, code)
		if err != nil {
			return fmt.Errorf("invalid pattern: %w", err)
		}
		if !matched {
			return fmt.Errorf("account code does not match required format: %s", format.Description)
		}
	}

	return nil
}

func (v *AccountCodeValidator) InferAccountType(code string) (AccountType, error) {
	if code == "" {
		return "", errors.New("account code is required")
	}

	firstChar := string(code[0])

	switch firstChar {
	case "1":
		return AccountTypeAsset, nil
	case "2":
		return AccountTypeLiability, nil
	case "3":
		return AccountTypeEquity, nil
	case "4":
		return AccountTypeRevenue, nil
	case "5":
		return AccountTypeExpense, nil
	default:
		return "", fmt.Errorf("cannot infer account type from code: %s", code)
	}
}

func (v *AccountCodeValidator) GenerateNextCode(existingCodes []string, accountType AccountType, parentCode string) (string, error) {
	format, exists := v.formats[accountType]
	if !exists {
		return "", fmt.Errorf("unknown account type: %s", accountType)
	}

	if parentCode != "" {
		childCodes := filterCodesByPrefix(existingCodes, parentCode)
		maxSuffix := 0
		for _, code := range childCodes {
			if len(code) > len(parentCode) {
				suffix := code[len(parentCode):]
				if num, err := strconv.Atoi(suffix); err == nil && num > maxSuffix {
					maxSuffix = num
				}
			}
		}
		nextCode := fmt.Sprintf("%s%d", parentCode, maxSuffix+1)
		if len(nextCode) <= format.MaxLength {
			return nextCode, nil
		}
	}

	prefixCodes := filterCodesByPrefix(existingCodes, format.Prefix)
	maxCode := 0
	baseMultiplier := 1
	for i := 0; i < format.MinLength-1; i++ {
		baseMultiplier *= 10
	}

	for _, code := range prefixCodes {
		if num, err := strconv.Atoi(code); err == nil && num > maxCode {
			maxCode = num
		}
	}

	if maxCode == 0 {
		prefixNum, _ := strconv.Atoi(format.Prefix)
		maxCode = prefixNum * baseMultiplier
	}

	return strconv.Itoa(maxCode + 1), nil
}

func filterCodesByPrefix(codes []string, prefix string) []string {
	var result []string
	for _, code := range codes {
		if strings.HasPrefix(code, prefix) {
			result = append(result, code)
		}
	}
	return result
}

type AccountValidationResult struct {
	IsValid bool
	Errors  []string
}

func ValidateAccount(account *Account) AccountValidationResult {
	result := AccountValidationResult{IsValid: true}

	if account.Code == "" {
		result.Errors = append(result.Errors, "Account code is required")
		result.IsValid = false
	}

	if account.Name == "" {
		result.Errors = append(result.Errors, "Account name is required")
		result.IsValid = false
	}

	if account.Type == "" {
		result.Errors = append(result.Errors, "Account type is required")
		result.IsValid = false
	} else {
		validTypes := map[AccountType]bool{
			AccountTypeAsset:     true,
			AccountTypeLiability: true,
			AccountTypeEquity:    true,
			AccountTypeRevenue:   true,
			AccountTypeExpense:   true,
		}
		if !validTypes[account.Type] {
			result.Errors = append(result.Errors, fmt.Sprintf("Invalid account type: %s", account.Type))
			result.IsValid = false
		}
	}

	if account.Currency == "" {
		result.Errors = append(result.Errors, "Currency is required")
		result.IsValid = false
	} else if len(account.Currency) != 3 {
		result.Errors = append(result.Errors, "Currency must be a 3-letter ISO code")
		result.IsValid = false
	}

	if account.Code != "" && account.Type != "" {
		validator := NewAccountCodeValidator()
		if err := validator.ValidateCode(account.Code, account.Type); err != nil {
			result.Errors = append(result.Errors, err.Error())
			result.IsValid = false
		}
	}

	return result
}

type JournalEntryValidationResult struct {
	IsValid bool
	Errors  []string
}

func ValidateJournalEntry(entry *JournalEntry) JournalEntryValidationResult {
	result := JournalEntryValidationResult{IsValid: true}

	if entry.EntryNumber == "" {
		result.Errors = append(result.Errors, "Entry number is required")
		result.IsValid = false
	}

	if entry.EntryDate.IsZero() {
		result.Errors = append(result.Errors, "Entry date is required")
		result.IsValid = false
	}

	if len(entry.Lines) < 2 {
		result.Errors = append(result.Errors, "Journal entry must have at least 2 lines")
		result.IsValid = false
	}

	var totalDebit, totalCredit int64
	hasDebit := false
	hasCredit := false

	for i, line := range entry.Lines {
		if line.AccountID == "" {
			result.Errors = append(result.Errors, fmt.Sprintf("Line %d: Account ID is required", i+1))
			result.IsValid = false
		}

		if line.DebitAmount < 0 {
			result.Errors = append(result.Errors, fmt.Sprintf("Line %d: Debit amount cannot be negative", i+1))
			result.IsValid = false
		}

		if line.CreditAmount < 0 {
			result.Errors = append(result.Errors, fmt.Sprintf("Line %d: Credit amount cannot be negative", i+1))
			result.IsValid = false
		}

		if line.DebitAmount == 0 && line.CreditAmount == 0 {
			result.Errors = append(result.Errors, fmt.Sprintf("Line %d: Either debit or credit amount is required", i+1))
			result.IsValid = false
		}

		if line.DebitAmount > 0 && line.CreditAmount > 0 {
			result.Errors = append(result.Errors, fmt.Sprintf("Line %d: Cannot have both debit and credit on same line", i+1))
			result.IsValid = false
		}

		totalDebit += line.DebitAmount
		totalCredit += line.CreditAmount

		if line.DebitAmount > 0 {
			hasDebit = true
		}
		if line.CreditAmount > 0 {
			hasCredit = true
		}
	}

	if !hasDebit {
		result.Errors = append(result.Errors, "Journal entry must have at least one debit line")
		result.IsValid = false
	}

	if !hasCredit {
		result.Errors = append(result.Errors, "Journal entry must have at least one credit line")
		result.IsValid = false
	}

	if totalDebit != totalCredit {
		result.Errors = append(result.Errors, fmt.Sprintf("Journal entry is not balanced: debits (%d) != credits (%d)", totalDebit, totalCredit))
		result.IsValid = false
	}

	return result
}

type CBNCodeValidator struct {
	validCodes map[string]string
}

func NewCBNCodeValidator() *CBNCodeValidator {
	return &CBNCodeValidator{
		validCodes: map[string]string{
			"SFP001": "Cash and Balances with Central Bank",
			"SFP002": "Due from Banks",
			"SFP003": "Financial Assets at Fair Value",
			"SFP004": "Derivative Financial Instruments",
			"SFP005": "Loans and Advances to Customers",
			"SFP006": "Investment Securities",
			"SFP007": "Property and Equipment",
			"SFP008": "Intangible Assets",
			"SFP009": "Deferred Tax Assets",
			"SFP010": "Other Assets",
			"SFP011": "Deposits from Banks",
			"SFP012": "Deposits from Customers",
			"SFP013": "Derivative Financial Instruments (Liabilities)",
			"SFP014": "Borrowings",
			"SFP015": "Current Tax Liabilities",
			"SFP016": "Deferred Tax Liabilities",
			"SFP017": "Other Liabilities",
			"SFP018": "Provisions",
			"SFP019": "Share Capital",
			"SFP020": "Share Premium",
			"SFP021": "Retained Earnings",
			"SFP022": "Other Reserves",
			"PL001":  "Interest Income",
			"PL002":  "Interest Expense",
			"PL003":  "Net Interest Income",
			"PL004":  "Fee and Commission Income",
			"PL005":  "Fee and Commission Expense",
			"PL006":  "Net Fee and Commission Income",
			"PL007":  "Net Trading Income",
			"PL008":  "Other Operating Income",
			"PL009":  "Impairment Charges",
			"PL010":  "Personnel Expenses",
			"PL011":  "Depreciation and Amortization",
			"PL012":  "Other Operating Expenses",
			"PL013":  "Profit Before Tax",
			"PL014":  "Income Tax Expense",
			"PL015":  "Profit After Tax",
			"CAR001": "Tier 1 Capital",
			"CAR002": "Tier 2 Capital",
			"CAR003": "Total Qualifying Capital",
			"CAR004": "Risk Weighted Assets",
			"CAR005": "Capital Adequacy Ratio",
			"LR001":  "Total Liquid Assets",
			"LR002":  "Total Liabilities",
			"LR003":  "Liquidity Ratio",
		},
	}
}

func (v *CBNCodeValidator) ValidateCode(code string) error {
	if code == "" {
		return nil
	}

	if _, exists := v.validCodes[code]; !exists {
		return fmt.Errorf("invalid CBN code: %s", code)
	}

	return nil
}

func (v *CBNCodeValidator) GetCodeDescription(code string) string {
	return v.validCodes[code]
}

func (v *CBNCodeValidator) ListValidCodes() map[string]string {
	result := make(map[string]string)
	for k, v := range v.validCodes {
		result[k] = v
	}
	return result
}

type CurrencyValidator struct {
	supportedCurrencies map[string]string
}

func NewCurrencyValidator() *CurrencyValidator {
	return &CurrencyValidator{
		supportedCurrencies: map[string]string{
			"NGN": "Nigerian Naira",
			"USD": "United States Dollar",
			"EUR": "Euro",
			"GBP": "British Pound Sterling",
			"XOF": "West African CFA Franc",
			"XAF": "Central African CFA Franc",
			"ZAR": "South African Rand",
			"KES": "Kenyan Shilling",
			"GHS": "Ghanaian Cedi",
			"EGP": "Egyptian Pound",
			"MAD": "Moroccan Dirham",
			"TZS": "Tanzanian Shilling",
			"UGX": "Ugandan Shilling",
			"RWF": "Rwandan Franc",
			"ETB": "Ethiopian Birr",
			"CNY": "Chinese Yuan",
			"JPY": "Japanese Yen",
			"INR": "Indian Rupee",
			"AED": "UAE Dirham",
			"SAR": "Saudi Riyal",
			"CHF": "Swiss Franc",
			"CAD": "Canadian Dollar",
			"AUD": "Australian Dollar",
		},
	}
}

func (v *CurrencyValidator) ValidateCurrency(code string) error {
	if code == "" {
		return errors.New("currency code is required")
	}

	code = strings.ToUpper(code)
	if _, exists := v.supportedCurrencies[code]; !exists {
		return fmt.Errorf("unsupported currency: %s", code)
	}

	return nil
}

func (v *CurrencyValidator) GetCurrencyName(code string) string {
	return v.supportedCurrencies[strings.ToUpper(code)]
}

func (v *CurrencyValidator) ListSupportedCurrencies() map[string]string {
	result := make(map[string]string)
	for k, v := range v.supportedCurrencies {
		result[k] = v
	}
	return result
}
