#[cfg(test)]
mod tests {
    use crate::{currency_registry, format_currency_amount, insert_thousands_sep, locale_registry};
    use rust_decimal::Decimal;
    use std::str::FromStr;

    // ── insert_thousands_sep ────────────────────────────────────────────────

    #[test]
    fn test_thousands_sep_comma() {
        assert_eq!(insert_thousands_sep("1000000", ","), "1,000,000");
    }

    #[test]
    fn test_thousands_sep_space() {
        assert_eq!(insert_thousands_sep("1000000", " "), "1 000 000");
    }

    #[test]
    fn test_thousands_sep_empty_no_change() {
        assert_eq!(insert_thousands_sep("1000000", ""), "1000000");
    }

    #[test]
    fn test_thousands_sep_short_number() {
        assert_eq!(insert_thousands_sep("999", ","), "999");
    }

    #[test]
    fn test_thousands_sep_four_digits() {
        assert_eq!(insert_thousands_sep("1000", ","), "1,000");
    }

    // ── currency_registry ───────────────────────────────────────────────────

    #[test]
    fn test_currency_registry_has_ngn() {
        let reg = currency_registry();
        let ngn = reg.get("NGN").unwrap();
        assert_eq!(ngn.code, "NGN");
        assert_eq!(ngn.symbol, "\u{20a6}");
        assert_eq!(ngn.decimal_places, 2);
        assert_eq!(ngn.thousands_sep, ",");
    }

    #[test]
    fn test_currency_registry_has_xof_zero_decimals() {
        let reg = currency_registry();
        let xof = reg.get("XOF").unwrap();
        assert_eq!(xof.decimal_places, 0);
        assert_eq!(xof.symbol_position, "after");
    }

    #[test]
    fn test_currency_registry_has_all_african_currencies() {
        let reg = currency_registry();
        for code in &["NGN", "GHS", "XOF", "KES", "ZAR", "ETB", "RWF", "UGX"] {
            assert!(reg.contains_key(code), "Missing currency: {}", code);
        }
    }

    #[test]
    fn test_currency_registry_has_major_currencies() {
        let reg = currency_registry();
        for code in &["USD", "EUR", "GBP"] {
            assert!(reg.contains_key(code), "Missing currency: {}", code);
        }
    }

    // ── format_currency_amount ──────────────────────────────────────────────

    #[test]
    fn test_format_ngn_amount() {
        let reg = currency_registry();
        let ngn = reg.get("NGN").unwrap();
        let amount = Decimal::from_str("25000.50").unwrap();
        let formatted = format_currency_amount(amount, ngn, false);
        assert!(formatted.contains("25,000.50"));
        assert!(formatted.contains("\u{20a6}"));
    }

    #[test]
    fn test_format_ngn_large_amount() {
        let reg = currency_registry();
        let ngn = reg.get("NGN").unwrap();
        let amount = Decimal::from_str("1000000.00").unwrap();
        let formatted = format_currency_amount(amount, ngn, false);
        assert!(formatted.contains("1,000,000.00"));
    }

    #[test]
    fn test_format_xof_no_decimals() {
        let reg = currency_registry();
        let xof = reg.get("XOF").unwrap();
        let amount = Decimal::from_str("50000").unwrap();
        let formatted = format_currency_amount(amount, xof, false);
        // XOF has 0 decimal places and symbol after
        assert!(formatted.contains("CFA"));
        assert!(!formatted.contains("."));
    }

    #[test]
    fn test_format_with_show_code() {
        let reg = currency_registry();
        let usd = reg.get("USD").unwrap();
        let amount = Decimal::from_str("100.00").unwrap();
        let formatted = format_currency_amount(amount, usd, true);
        assert!(formatted.contains("USD"));
        assert!(formatted.contains("$"));
    }

    #[test]
    fn test_format_negative_amount() {
        let reg = currency_registry();
        let ngn = reg.get("NGN").unwrap();
        let amount = Decimal::from_str("-500.00").unwrap();
        let formatted = format_currency_amount(amount, ngn, false);
        assert!(formatted.contains("-"));
        assert!(formatted.contains("500.00"));
    }

    #[test]
    fn test_format_zar_space_thousands_sep() {
        let reg = currency_registry();
        let zar = reg.get("ZAR").unwrap();
        let amount = Decimal::from_str("1000.00").unwrap();
        let formatted = format_currency_amount(amount, zar, false);
        // ZAR uses space as thousands separator
        assert!(formatted.contains("R"));
    }

    // ── locale_registry ─────────────────────────────────────────────────────

    #[test]
    fn test_locale_registry_has_nigerian_locales() {
        let reg = locale_registry();
        for locale in &["en-NG", "yo-NG", "ha-NG", "ig-NG"] {
            assert!(reg.contains_key(locale), "Missing locale: {}", locale);
        }
    }

    #[test]
    fn test_locale_en_ng_default_currency() {
        let reg = locale_registry();
        let locale = reg.get("en-NG").unwrap();
        assert_eq!(locale.default_currency, "NGN");
        assert!(!locale.rtl);
    }

    #[test]
    fn test_locale_registry_has_african_locales() {
        let reg = locale_registry();
        for locale in &["en-GH", "fr-SN", "en-KE", "sw-KE", "en-ZA"] {
            assert!(reg.contains_key(locale), "Missing locale: {}", locale);
        }
    }
}
