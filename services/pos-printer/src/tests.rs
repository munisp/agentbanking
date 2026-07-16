#[cfg(test)]
mod tests {
    use crate::{EscPosBuilder, PaperWidth};

    fn make_builder_58mm() -> EscPosBuilder {
        EscPosBuilder::new(PaperWidth::W58mm)
    }

    fn make_builder_80mm() -> EscPosBuilder {
        EscPosBuilder::new(PaperWidth::W80mm)
    }

    #[test]
    fn test_paper_width_58mm_chars_per_line() {
        assert_eq!(PaperWidth::W58mm.chars_per_line(), 32);
    }

    #[test]
    fn test_paper_width_80mm_chars_per_line() {
        assert_eq!(PaperWidth::W80mm.chars_per_line(), 48);
    }

    #[test]
    fn test_builder_line_appends_text_and_newline() {
        let mut b = make_builder_58mm();
        b.line("Hello");
        let data = b.build();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains("Hello"));
        // Should end with a newline somewhere
        assert!(data.contains(&b'\n'));
    }

    #[test]
    fn test_builder_separator_correct_length() {
        let mut b = make_builder_58mm();
        b.separator();
        let data = b.build();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains(&"-".repeat(32)));
    }

    #[test]
    fn test_builder_double_separator_correct_length() {
        let mut b = make_builder_80mm();
        b.double_separator();
        let data = b.build();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains(&"=".repeat(48)));
    }

    #[test]
    fn test_builder_centered_text() {
        let mut b = make_builder_58mm();
        b.centered("54agent");
        let data = b.build();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains("54agent"));
    }

    #[test]
    fn test_builder_row_two_columns() {
        let mut b = make_builder_58mm();
        b.row("Amount:", "5,000.00");
        let data = b.build();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains("Amount:"));
        assert!(text.contains("5,000.00"));
    }

    #[test]
    fn test_builder_amount_line_formats_currency() {
        let mut b = make_builder_58mm();
        b.amount_line("TOTAL", 25000.50, "NGN");
        let data = b.build();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains("TOTAL"));
        assert!(text.contains("NGN"));
        assert!(text.contains("25000.50"));
    }

    #[test]
    fn test_builder_build_base64_is_valid_base64() {
        let mut b = make_builder_58mm();
        b.line("Test Receipt");
        let b64 = b.build_base64();
        assert!(b64.chars().all(|c| c.is_alphanumeric() || c == '+' || c == '/' || c == '='));
    }

    #[test]
    fn test_builder_multiple_operations_chain() {
        let mut b = make_builder_80mm();
        b.centered("54agent POS")
            .separator()
            .row("Date:", "2026-04-09")
            .row("Time:", "14:30:00")
            .separator()
            .amount_line("TOTAL", 10_000.0, "NGN")
            .double_separator()
            .centered("Thank You");
        let data = b.build();
        let text = String::from_utf8_lossy(&data);
        assert!(text.contains("54agent POS"));
        assert!(text.contains("Date:"));
        assert!(text.contains("TOTAL"));
        assert!(text.contains("Thank You"));
    }

    #[test]
    fn test_paper_width_equality() {
        assert_eq!(PaperWidth::W58mm, PaperWidth::W58mm);
        assert_ne!(PaperWidth::W58mm, PaperWidth::W80mm);
    }
}
