// 54Link Agency Banking Platform — ESC/POS Thermal Printer Service
// Language: Rust
// Purpose: Full ESC/POS protocol implementation for all 10 P-UP IFS / FLEX POS terminals.
//          Handles 58mm and 80mm paper widths, receipt templates, QR codes, logos,
//          and per-terminal printer capability routing.

#[cfg(test)]
mod tests;

use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, net::SocketAddr, sync::Arc};
use tokio::sync::RwLock;
use tracing::{error, info};
use uuid::Uuid;

// ── ESC/POS Command Constants ─────────────────────────────────────────────────
const ESC: u8 = 0x1B;
const GS: u8 = 0x1D;
const LF: u8 = 0x0A;
const CR: u8 = 0x0D;
const HT: u8 = 0x09;

// Initialize printer
const INIT: [u8; 2] = [ESC, b'@'];
// Line feed
const FEED: [u8; 1] = [LF];
// Cut paper (full cut)
const CUT_FULL: [u8; 4] = [GS, b'V', 0x00, 0x00];
// Cut paper (partial cut)
const CUT_PARTIAL: [u8; 4] = [GS, b'V', 0x01, 0x00];
// Bold on/off
const BOLD_ON: [u8; 3] = [ESC, b'E', 0x01];
const BOLD_OFF: [u8; 3] = [ESC, b'E', 0x00];
// Underline on/off
const UNDERLINE_ON: [u8; 3] = [ESC, b'-', 0x01];
const UNDERLINE_OFF: [u8; 3] = [ESC, b'-', 0x00];
// Align left/center/right
const ALIGN_LEFT: [u8; 3] = [ESC, b'a', 0x00];
const ALIGN_CENTER: [u8; 3] = [ESC, b'a', 0x01];
const ALIGN_RIGHT: [u8; 3] = [ESC, b'a', 0x02];
// Font size double height/width
const FONT_NORMAL: [u8; 3] = [GS, b'!', 0x00];
const FONT_DOUBLE_HEIGHT: [u8; 3] = [GS, b'!', 0x01];
const FONT_DOUBLE_WIDTH: [u8; 3] = [GS, b'!', 0x10];
const FONT_DOUBLE_BOTH: [u8; 3] = [GS, b'!', 0x11];
// Reverse printing
const REVERSE_ON: [u8; 3] = [GS, b'B', 0x01];
const REVERSE_OFF: [u8; 3] = [GS, b'B', 0x00];

// ── Paper Width Configuration ─────────────────────────────────────────────────
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum PaperWidth {
    #[serde(rename = "58mm")]
    W58mm,
    #[serde(rename = "80mm")]
    W80mm,
}

impl PaperWidth {
    fn chars_per_line(&self) -> usize {
        match self {
            PaperWidth::W58mm => 32,
            PaperWidth::W80mm => 48,
        }
    }
    fn dots_per_line(&self) -> u16 {
        match self {
            PaperWidth::W58mm => 384,
            PaperWidth::W80mm => 576,
        }
    }
}

// ── Terminal Printer Config ───────────────────────────────────────────────────
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TerminalPrinterConfig {
    pub model_id: String,
    pub model_name: String,
    pub paper_width: PaperWidth,
    pub has_printer: bool,
    pub via_paired: bool,
    pub speed_mm_s: u32,
    pub supports_logo: bool,
    pub supports_qr: bool,
    pub supports_barcode: bool,
    pub cut_type: CutType,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CutType {
    Full,
    Partial,
    None,
}

fn get_terminal_printer_configs() -> HashMap<String, TerminalPrinterConfig> {
    let mut configs = HashMap::new();

    configs.insert("horizonpay_k11".to_string(), TerminalPrinterConfig {
        model_id: "horizonpay_k11".to_string(),
        model_name: "HorizonPay K11".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 80, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Partial,
    });
    configs.insert("newland_n910".to_string(), TerminalPrinterConfig {
        model_id: "newland_n910".to_string(),
        model_name: "Newland N910".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 80, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Partial,
    });
    configs.insert("newland_n910_pro".to_string(), TerminalPrinterConfig {
        model_id: "newland_n910_pro".to_string(),
        model_name: "Newland N910 Pro".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 80, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Partial,
    });
    configs.insert("pax_a920_max".to_string(), TerminalPrinterConfig {
        model_id: "pax_a920_max".to_string(),
        model_name: "PAX A920 MAX".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 100, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Full,
    });
    configs.insert("pax_a8900".to_string(), TerminalPrinterConfig {
        model_id: "pax_a8900".to_string(),
        model_name: "PAX A8900".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 80, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Full,
    });
    configs.insert("topwise_t11_pro".to_string(), TerminalPrinterConfig {
        model_id: "topwise_t11_pro".to_string(),
        model_name: "Topwise T11 Pro".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 80, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Partial,
    });
    configs.insert("topwise_mp45p".to_string(), TerminalPrinterConfig {
        model_id: "topwise_mp45p".to_string(),
        model_name: "Topwise MP45P".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 60, supports_logo: true, supports_qr: true, supports_barcode: false,
        cut_type: CutType::Partial,
    });
    configs.insert("newland_n750".to_string(), TerminalPrinterConfig {
        model_id: "newland_n750".to_string(),
        model_name: "Newland MiniPOS N750".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 60, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Partial,
    });
    configs.insert("newland_me30su".to_string(), TerminalPrinterConfig {
        model_id: "newland_me30su".to_string(),
        model_name: "Newland ME30SU (mPOS)".to_string(),
        paper_width: PaperWidth::W58mm, // via paired phone
        has_printer: false, via_paired: true,
        speed_mm_s: 0, supports_logo: false, supports_qr: true, supports_barcode: false,
        cut_type: CutType::None,
    });
    configs.insert("horizonpay_k11_lite".to_string(), TerminalPrinterConfig {
        model_id: "horizonpay_k11_lite".to_string(),
        model_name: "HorizonPay K11 Lite".to_string(),
        paper_width: PaperWidth::W58mm,
        has_printer: true, via_paired: false,
        speed_mm_s: 80, supports_logo: true, supports_qr: true, supports_barcode: true,
        cut_type: CutType::Partial,
    });

    configs
}

// ── Receipt Data Models ───────────────────────────────────────────────────────
#[derive(Debug, Deserialize)]
pub struct PrintReceiptRequest {
    pub terminal_id: String,
    pub model_id: String,
    pub receipt_type: ReceiptType,
    pub data: ReceiptData,
    pub copies: Option<u8>,
    pub include_qr: Option<bool>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "snake_case")]
pub enum ReceiptType {
    Payment,
    Refund,
    BalanceEnquiry,
    MiniStatement,
    AgentReport,
    CashDeposit,
    CashWithdrawal,
    BillPayment,
    AirtimeTopup,
    TransferReceipt,
    PosSettlement,
    EndOfDay,
    TestPrint,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct ReceiptData {
    // Header
    pub merchant_name: Option<String>,
    pub merchant_address: Option<String>,
    pub merchant_id: Option<String>,
    pub terminal_id: Option<String>,
    pub agent_name: Option<String>,
    pub agent_id: Option<String>,

    // Transaction
    pub transaction_id: Option<String>,
    pub reference: Option<String>,
    pub rrn: Option<String>,          // Retrieval Reference Number
    pub stan: Option<String>,         // System Trace Audit Number
    pub auth_code: Option<String>,

    // Card / Payment
    pub card_scheme: Option<String>,  // VISA, MASTERCARD, VERVE
    pub pan_masked: Option<String>,   // **** **** **** 1234
    pub card_holder: Option<String>,
    pub expiry: Option<String>,
    pub entry_mode: Option<String>,   // CHIP, CONTACTLESS, SWIPE, MANUAL

    // Amount
    pub currency: Option<String>,
    pub amount: Option<f64>,
    pub surcharge: Option<f64>,
    pub cashback: Option<f64>,
    pub total_amount: Option<f64>,

    // Status
    pub status: Option<String>,       // APPROVED, DECLINED, REVERSED
    pub response_code: Option<String>,
    pub response_message: Option<String>,

    // Timestamps
    pub transaction_date: Option<String>,
    pub transaction_time: Option<String>,

    // Mini statement lines
    pub statement_lines: Option<Vec<StatementLine>>,

    // Agent report data
    pub report_period: Option<String>,
    pub total_transactions: Option<u32>,
    pub total_volume: Option<f64>,
    pub successful_txns: Option<u32>,
    pub failed_txns: Option<u32>,
    pub commission_earned: Option<f64>,

    // Bill payment
    pub biller_name: Option<String>,
    pub account_number: Option<String>,
    pub service_type: Option<String>,

    // Airtime
    pub phone_number: Option<String>,
    pub network: Option<String>,
    pub airtime_amount: Option<f64>,

    // Custom footer
    pub footer_message: Option<String>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct StatementLine {
    pub date: String,
    pub description: String,
    pub amount: f64,
    pub balance: f64,
    pub credit: bool,
}

// ── ESC/POS Builder ───────────────────────────────────────────────────────────
pub struct EscPosBuilder {
    buffer: Vec<u8>,
    paper_width: PaperWidth,
    chars_per_line: usize,
}

impl EscPosBuilder {
    pub fn new(paper_width: PaperWidth) -> Self {
        let chars_per_line = paper_width.chars_per_line();
        let mut builder = Self {
            buffer: Vec::new(),
            paper_width,
            chars_per_line,
        };
        builder.buffer.extend_from_slice(&INIT);
        builder
    }

    pub fn init(&mut self) -> &mut Self {
        self.buffer.extend_from_slice(&INIT);
        self
    }

    pub fn feed(&mut self, lines: u8) -> &mut Self {
        for _ in 0..lines {
            self.buffer.push(LF);
        }
        self
    }

    pub fn cut(&mut self, partial: bool) -> &mut Self {
        if partial {
            self.buffer.extend_from_slice(&CUT_PARTIAL);
        } else {
            self.buffer.extend_from_slice(&CUT_FULL);
        }
        self
    }

    pub fn align_left(&mut self) -> &mut Self {
        self.buffer.extend_from_slice(&ALIGN_LEFT);
        self
    }

    pub fn align_center(&mut self) -> &mut Self {
        self.buffer.extend_from_slice(&ALIGN_CENTER);
        self
    }

    pub fn align_right(&mut self) -> &mut Self {
        self.buffer.extend_from_slice(&ALIGN_RIGHT);
        self
    }

    pub fn bold(&mut self, on: bool) -> &mut Self {
        if on {
            self.buffer.extend_from_slice(&BOLD_ON);
        } else {
            self.buffer.extend_from_slice(&BOLD_OFF);
        }
        self
    }

    pub fn underline(&mut self, on: bool) -> &mut Self {
        if on {
            self.buffer.extend_from_slice(&UNDERLINE_ON);
        } else {
            self.buffer.extend_from_slice(&UNDERLINE_OFF);
        }
        self
    }

    pub fn font_size(&mut self, double_height: bool, double_width: bool) -> &mut Self {
        match (double_height, double_width) {
            (true, true)  => self.buffer.extend_from_slice(&FONT_DOUBLE_BOTH),
            (true, false) => self.buffer.extend_from_slice(&FONT_DOUBLE_HEIGHT),
            (false, true) => self.buffer.extend_from_slice(&FONT_DOUBLE_WIDTH),
            (false, false) => self.buffer.extend_from_slice(&FONT_NORMAL),
        }
        self
    }

    pub fn reverse(&mut self, on: bool) -> &mut Self {
        if on {
            self.buffer.extend_from_slice(&REVERSE_ON);
        } else {
            self.buffer.extend_from_slice(&REVERSE_OFF);
        }
        self
    }

    pub fn text(&mut self, text: &str) -> &mut Self {
        self.buffer.extend_from_slice(text.as_bytes());
        self
    }

    pub fn line(&mut self, text: &str) -> &mut Self {
        self.buffer.extend_from_slice(text.as_bytes());
        self.buffer.push(LF);
        self
    }

    pub fn separator(&mut self) -> &mut Self {
        let line = "-".repeat(self.chars_per_line);
        self.buffer.extend_from_slice(line.as_bytes());
        self.buffer.push(LF);
        self
    }

    pub fn double_separator(&mut self) -> &mut Self {
        let line = "=".repeat(self.chars_per_line);
        self.buffer.extend_from_slice(line.as_bytes());
        self.buffer.push(LF);
        self
    }

    /// Print two-column row: left-aligned label, right-aligned value
    pub fn row(&mut self, label: &str, value: &str) -> &mut Self {
        let total = self.chars_per_line;
        let label_len = label.len().min(total - 1);
        let value_len = value.len().min(total - label_len);
        let spaces = total.saturating_sub(label_len + value_len);
        let row = format!("{}{}{}", &label[..label_len], " ".repeat(spaces), &value[..value_len]);
        self.buffer.extend_from_slice(row.as_bytes());
        self.buffer.push(LF);
        self
    }

    /// Center a string within the line width
    pub fn centered(&mut self, text: &str) -> &mut Self {
        let total = self.chars_per_line;
        let text_len = text.len().min(total);
        let padding = (total.saturating_sub(text_len)) / 2;
        let centered = format!("{}{}", " ".repeat(padding), &text[..text_len]);
        self.buffer.extend_from_slice(centered.as_bytes());
        self.buffer.push(LF);
        self
    }

    /// Format currency amount
    pub fn amount_line(&mut self, label: &str, amount: f64, currency: &str) -> &mut Self {
        let value = format!("{} {:>12.2}", currency, amount);
        self.row(label, &value)
    }

    pub fn build(self) -> Vec<u8> {
        self.buffer
    }

    pub fn build_base64(self) -> String {
        use base64::{Engine as _, engine::general_purpose};
        general_purpose::STANDARD.encode(self.buffer)
    }
}

// ── Receipt Template Engine ───────────────────────────────────────────────────
pub struct ReceiptEngine {
    printer_configs: HashMap<String, TerminalPrinterConfig>,
}

impl ReceiptEngine {
    pub fn new() -> Self {
        Self {
            printer_configs: get_terminal_printer_configs(),
        }
    }

    pub fn render(&self, req: &PrintReceiptRequest) -> Result<RenderedReceipt, String> {
        let config = self.printer_configs.get(&req.model_id)
            .ok_or_else(|| format!("Unknown terminal model: {}", req.model_id))?;

        if !config.has_printer && !config.via_paired {
            return Err(format!("Terminal {} has no printer capability", req.model_id));
        }

        let paper_width = config.paper_width.clone();
        let escpos_bytes = match req.receipt_type {
            ReceiptType::Payment => self.render_payment(&req.data, &paper_width, config),
            ReceiptType::Refund => self.render_refund(&req.data, &paper_width, config),
            ReceiptType::BalanceEnquiry => self.render_balance(&req.data, &paper_width, config),
            ReceiptType::MiniStatement => self.render_mini_statement(&req.data, &paper_width, config),
            ReceiptType::AgentReport => self.render_agent_report(&req.data, &paper_width, config),
            ReceiptType::CashDeposit => self.render_cash_deposit(&req.data, &paper_width, config),
            ReceiptType::CashWithdrawal => self.render_cash_withdrawal(&req.data, &paper_width, config),
            ReceiptType::BillPayment => self.render_bill_payment(&req.data, &paper_width, config),
            ReceiptType::AirtimeTopup => self.render_airtime(&req.data, &paper_width, config),
            ReceiptType::TransferReceipt => self.render_transfer(&req.data, &paper_width, config),
            ReceiptType::PosSettlement => self.render_settlement(&req.data, &paper_width, config),
            ReceiptType::EndOfDay => self.render_end_of_day(&req.data, &paper_width, config),
            ReceiptType::TestPrint => self.render_test_print(&paper_width, config),
        };

        let receipt_id = Uuid::new_v4().to_string();
        Ok(RenderedReceipt {
            receipt_id: receipt_id.clone(),
            terminal_id: req.terminal_id.clone(),
            model_id: req.model_id.clone(),
            receipt_type: req.receipt_type.clone(),
            paper_width: config.paper_width.clone(),
            via_paired: config.via_paired,
            escpos_hex: hex::encode(&escpos_bytes),
            escpos_base64: {
                use base64::{Engine as _, engine::general_purpose};
                general_purpose::STANDARD.encode(&escpos_bytes)
            },
            byte_count: escpos_bytes.len(),
            copies: req.copies.unwrap_or(1),
            rendered_at: Utc::now(),
        })
    }

    fn render_header(&self, builder: &mut EscPosBuilder, data: &ReceiptData, config: &TerminalPrinterConfig) {
        builder.align_center();
        builder.bold(true);
        builder.font_size(true, false); // double height
        builder.line(&data.merchant_name.clone().unwrap_or("54LINK AGENCY".to_string()));
        builder.font_size(false, false);
        builder.bold(false);
        if let Some(addr) = &data.merchant_address {
            builder.line(addr);
        }
        builder.line("54Link Agency Banking Platform");
        builder.line(&format!("Terminal: {}", data.terminal_id.clone().unwrap_or_default()));
        builder.line(&format!("Agent: {}", data.agent_name.clone().unwrap_or_default()));
        builder.align_left();
        builder.double_separator();
    }

    fn render_footer(&self, builder: &mut EscPosBuilder, data: &ReceiptData, config: &TerminalPrinterConfig, include_qr: bool) {
        builder.separator();
        builder.align_center();
        if let Some(ref_no) = &data.reference {
            if include_qr && config.supports_qr {
                // QR code command: GS ( k — store QR data then print
                // Store QR data
                let qr_data = ref_no.as_bytes();
                let data_len = qr_data.len() + 3;
                let pl = (data_len & 0xFF) as u8;
                let ph = ((data_len >> 8) & 0xFF) as u8;
                // Set QR model
                builder.buffer.extend_from_slice(&[GS, b'(', b'k', 4, 0, 49, 65, 50, 0]);
                // Set QR size
                builder.buffer.extend_from_slice(&[GS, b'(', b'k', 3, 0, 49, 67, 6]);
                // Set error correction
                builder.buffer.extend_from_slice(&[GS, b'(', b'k', 3, 0, 49, 69, 48]);
                // Store data
                builder.buffer.extend_from_slice(&[GS, b'(', b'k', pl, ph, 49, 80, 48]);
                builder.buffer.extend_from_slice(qr_data);
                // Print QR
                builder.buffer.extend_from_slice(&[GS, b'(', b'k', 3, 0, 49, 81, 48]);
                builder.feed(1);
            }
        }
        builder.line(&data.footer_message.clone().unwrap_or("Thank you for using 54Link".to_string()));
        builder.line("Powered by P-UP Innovative Financial Solutions");
        builder.line("www.pup.finance | enterprise@pup.finance");
        builder.feed(3);
        match config.cut_type {
            CutType::Full => builder.cut(false),
            CutType::Partial => builder.cut(true),
            CutType::None => builder.feed(0),
        };
    }

    fn render_payment(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);

        b.align_center();
        b.bold(true);
        let status = data.status.clone().unwrap_or("APPROVED".to_string());
        if status == "APPROVED" {
            b.line("*** PAYMENT APPROVED ***");
        } else {
            b.line(&format!("*** {} ***", status));
        }
        b.bold(false);
        b.align_left();
        b.feed(1);

        if let Some(amount) = data.total_amount.or(data.amount) {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.align_center();
            b.bold(true);
            b.font_size(true, true); // double height + width
            b.line(&format!("{} {:>10.2}", currency, amount));
            b.font_size(false, false);
            b.bold(false);
            b.align_left();
        }
        b.separator();

        if let Some(scheme) = &data.card_scheme { b.row("Card Type:", scheme); }
        if let Some(pan) = &data.pan_masked { b.row("Card No:", pan); }
        if let Some(holder) = &data.card_holder { b.row("Card Holder:", holder); }
        if let Some(mode) = &data.entry_mode { b.row("Entry Mode:", mode); }
        b.separator();

        if let Some(amt) = data.amount { b.amount_line("Amount:", amt, &data.currency.clone().unwrap_or("NGN".to_string())); }
        if let Some(sur) = data.surcharge { if sur > 0.0 { b.amount_line("Surcharge:", sur, &data.currency.clone().unwrap_or("NGN".to_string())); } }
        if let Some(cb) = data.cashback { if cb > 0.0 { b.amount_line("Cashback:", cb, &data.currency.clone().unwrap_or("NGN".to_string())); } }
        if let Some(total) = data.total_amount {
            b.bold(true);
            b.amount_line("TOTAL:", total, &data.currency.clone().unwrap_or("NGN".to_string()));
            b.bold(false);
        }
        b.separator();

        if let Some(txn_id) = &data.transaction_id { b.row("TXN ID:", txn_id); }
        if let Some(rrn) = &data.rrn { b.row("RRN:", rrn); }
        if let Some(stan) = &data.stan { b.row("STAN:", stan); }
        if let Some(auth) = &data.auth_code { b.row("Auth Code:", auth); }
        if let Some(rc) = &data.response_code { b.row("Response:", rc); }
        b.separator();

        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        if let Some(mid) = &data.merchant_id { b.row("MID:", mid); }
        if let Some(tid) = &data.terminal_id { b.row("TID:", tid); }

        self.render_footer(&mut b, data, config, true);
        b.build()
    }

    fn render_refund(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("*** REFUND RECEIPT ***");
        b.bold(false);
        b.align_left();
        b.feed(1);
        if let Some(amount) = data.total_amount.or(data.amount) {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.align_center();
            b.bold(true);
            b.font_size(true, true);
            b.line(&format!("{} {:>10.2}", currency, amount));
            b.font_size(false, false);
            b.bold(false);
            b.align_left();
        }
        b.separator();
        if let Some(pan) = &data.pan_masked { b.row("Card No:", pan); }
        if let Some(txn_id) = &data.transaction_id { b.row("Original TXN:", txn_id); }
        if let Some(auth) = &data.auth_code { b.row("Auth Code:", auth); }
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, false);
        b.build()
    }

    fn render_balance(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("BALANCE ENQUIRY");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(pan) = &data.pan_masked { b.row("Card No:", pan); }
        if let Some(holder) = &data.card_holder { b.row("Name:", holder); }
        b.separator();
        if let Some(amount) = data.amount {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Available Balance:", amount, &currency);
            b.bold(false);
        }
        b.separator();
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, false);
        b.build()
    }

    fn render_mini_statement(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("MINI STATEMENT");
        b.bold(false);
        b.align_left();
        if let Some(pan) = &data.pan_masked { b.row("Account:", pan); }
        if let Some(holder) = &data.card_holder { b.row("Name:", holder); }
        b.double_separator();
        b.row("Date", "Amount");
        b.separator();
        if let Some(lines) = &data.statement_lines {
            for line in lines.iter().take(10) {
                let sign = if line.credit { "+" } else { "-" };
                let amount_str = format!("{}{:.2}", sign, line.amount);
                b.row(&format!("{} {}", line.date, &line.description[..line.description.len().min(12)]), &amount_str);
            }
        }
        b.separator();
        if let Some(amount) = data.amount {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Current Balance:", amount, &currency);
            b.bold(false);
        }
        self.render_footer(&mut b, data, config, false);
        b.build()
    }

    fn render_agent_report(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("AGENT TRANSACTION REPORT");
        b.bold(false);
        b.align_left();
        if let Some(period) = &data.report_period { b.row("Period:", period); }
        b.double_separator();
        if let Some(total) = data.total_transactions { b.row("Total Transactions:", &total.to_string()); }
        if let Some(success) = data.successful_txns { b.row("Successful:", &success.to_string()); }
        if let Some(failed) = data.failed_txns { b.row("Failed:", &failed.to_string()); }
        b.separator();
        if let Some(volume) = data.total_volume {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Total Volume:", volume, &currency);
            b.bold(false);
        }
        if let Some(commission) = data.commission_earned {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Commission Earned:", commission, &currency);
            b.bold(false);
        }
        self.render_footer(&mut b, data, config, false);
        b.build()
    }

    fn render_cash_deposit(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("CASH DEPOSIT");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(account) = &data.account_number { b.row("Account:", account); }
        if let Some(holder) = &data.card_holder { b.row("Account Name:", holder); }
        b.separator();
        if let Some(amount) = data.amount {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.font_size(true, false);
            b.amount_line("Amount Deposited:", amount, &currency);
            b.font_size(false, false);
            b.bold(false);
        }
        b.separator();
        if let Some(txn_id) = &data.transaction_id { b.row("TXN ID:", txn_id); }
        if let Some(rrn) = &data.rrn { b.row("RRN:", rrn); }
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, true);
        b.build()
    }

    fn render_cash_withdrawal(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("CASH WITHDRAWAL");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(pan) = &data.pan_masked { b.row("Card No:", pan); }
        if let Some(holder) = &data.card_holder { b.row("Card Holder:", holder); }
        b.separator();
        if let Some(amount) = data.amount {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.font_size(true, false);
            b.amount_line("Amount Withdrawn:", amount, &currency);
            b.font_size(false, false);
            b.bold(false);
        }
        if let Some(sur) = data.surcharge { if sur > 0.0 {
            b.amount_line("Surcharge:", sur, &data.currency.clone().unwrap_or("NGN".to_string()));
        }}
        b.separator();
        if let Some(txn_id) = &data.transaction_id { b.row("TXN ID:", txn_id); }
        if let Some(auth) = &data.auth_code { b.row("Auth Code:", auth); }
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, true);
        b.build()
    }

    fn render_bill_payment(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("BILL PAYMENT");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(biller) = &data.biller_name { b.row("Biller:", biller); }
        if let Some(svc) = &data.service_type { b.row("Service:", svc); }
        if let Some(account) = &data.account_number { b.row("Account/Meter:", account); }
        b.separator();
        if let Some(amount) = data.amount {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Amount Paid:", amount, &currency);
            b.bold(false);
        }
        b.separator();
        if let Some(txn_id) = &data.transaction_id { b.row("TXN ID:", txn_id); }
        if let Some(rrn) = &data.rrn { b.row("RRN:", rrn); }
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, true);
        b.build()
    }

    fn render_airtime(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("AIRTIME TOP-UP");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(network) = &data.network { b.row("Network:", network); }
        if let Some(phone) = &data.phone_number { b.row("Phone:", phone); }
        b.separator();
        if let Some(amount) = data.airtime_amount.or(data.amount) {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Airtime Amount:", amount, &currency);
            b.bold(false);
        }
        b.separator();
        if let Some(txn_id) = &data.transaction_id { b.row("TXN ID:", txn_id); }
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, false);
        b.build()
    }

    fn render_transfer(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("FUNDS TRANSFER");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(holder) = &data.card_holder { b.row("Beneficiary:", holder); }
        if let Some(account) = &data.account_number { b.row("Account:", account); }
        b.separator();
        if let Some(amount) = data.amount {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.font_size(true, false);
            b.amount_line("Amount Sent:", amount, &currency);
            b.font_size(false, false);
            b.bold(false);
        }
        b.separator();
        if let Some(txn_id) = &data.transaction_id { b.row("TXN ID:", txn_id); }
        if let Some(rrn) = &data.rrn { b.row("RRN:", rrn); }
        if let Some(auth) = &data.auth_code { b.row("Auth Code:", auth); }
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, true);
        b.build()
    }

    fn render_settlement(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("POS SETTLEMENT");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(period) = &data.report_period { b.row("Batch Period:", period); }
        b.double_separator();
        if let Some(total) = data.total_transactions { b.row("Total Transactions:", &total.to_string()); }
        if let Some(volume) = data.total_volume {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Settlement Amount:", volume, &currency);
            b.bold(false);
        }
        b.separator();
        if let Some(txn_id) = &data.transaction_id { b.row("Batch ID:", txn_id); }
        if let Some(date) = &data.transaction_date { b.row("Date:", date); }
        if let Some(time) = &data.transaction_time { b.row("Time:", time); }
        self.render_footer(&mut b, data, config, false);
        b.build()
    }

    fn render_end_of_day(&self, data: &ReceiptData, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        self.render_header(&mut b, data, config);
        b.align_center();
        b.bold(true);
        b.line("END OF DAY REPORT");
        b.bold(false);
        b.align_left();
        b.separator();
        if let Some(period) = &data.report_period { b.row("Date:", period); }
        b.double_separator();
        if let Some(total) = data.total_transactions { b.row("Total Transactions:", &total.to_string()); }
        if let Some(success) = data.successful_txns { b.row("Successful:", &success.to_string()); }
        if let Some(failed) = data.failed_txns { b.row("Failed:", &failed.to_string()); }
        b.separator();
        if let Some(volume) = data.total_volume {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Total Volume:", volume, &currency);
            b.bold(false);
        }
        if let Some(commission) = data.commission_earned {
            let currency = data.currency.clone().unwrap_or("NGN".to_string());
            b.bold(true);
            b.amount_line("Commission Earned:", commission, &currency);
            b.bold(false);
        }
        self.render_footer(&mut b, data, config, false);
        b.build()
    }

    fn render_test_print(&self, paper_width: &PaperWidth, config: &TerminalPrinterConfig) -> Vec<u8> {
        let mut b = EscPosBuilder::new(paper_width.clone());
        b.align_center();
        b.bold(true);
        b.font_size(true, false);
        b.line("54LINK PLATFORM");
        b.font_size(false, false);
        b.line("TEST PRINT");
        b.bold(false);
        b.separator();
        b.row("Model:", &config.model_name);
        b.row("Paper Width:", match paper_width { PaperWidth::W58mm => "58mm", PaperWidth::W80mm => "80mm" });
        b.row("Chars/Line:", &b.chars_per_line.to_string());
        b.separator();
        b.line("ABCDEFGHIJKLMNOPQRSTUVWXYZ");
        b.line("abcdefghijklmnopqrstuvwxyz");
        b.line("0123456789");
        b.line("!@#$%^&*()_+-=[]{}|;:,.<>?");
        b.separator();
        b.align_center();
        b.line("Test print successful!");
        b.line(&format!("{}", Utc::now().format("%Y-%m-%d %H:%M:%S UTC")));
        b.feed(3);
        match config.cut_type {
            CutType::Full => b.cut(false),
            CutType::Partial => b.cut(true),
            CutType::None => b.feed(0),
        };
        b.build()
    }
}

// ── Response Types ─────────────────────────────────────────────────────────────
#[derive(Serialize)]
pub struct RenderedReceipt {
    pub receipt_id: String,
    pub terminal_id: String,
    pub model_id: String,
    pub receipt_type: ReceiptType,
    pub paper_width: PaperWidth,
    pub via_paired: bool,
    pub escpos_hex: String,
    pub escpos_base64: String,
    pub byte_count: usize,
    pub copies: u8,
    pub rendered_at: DateTime<Utc>,
}

#[derive(Serialize)]
pub struct ApiResponse<T: Serialize> {
    pub success: bool,
    pub data: Option<T>,
    pub error: Option<String>,
}

impl<T: Serialize> ApiResponse<T> {
    pub fn ok(data: T) -> Self {
        Self { success: true, data: Some(data), error: None }
    }
    pub fn err(msg: &str) -> ApiResponse<serde_json::Value> {
        ApiResponse { success: false, data: None, error: Some(msg.to_string()) }
    }
}

// ── App State ─────────────────────────────────────────────────────────────────
#[derive(Clone)]
pub struct AppState {
    pub engine: Arc<ReceiptEngine>,
    pub printer_configs: Arc<HashMap<String, TerminalPrinterConfig>>,
}

// ── Route Handlers ─────────────────────────────────────────────────────────────
async fn health_handler() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "rust-pos-printer",
        "version": "14.0.0",
        "supported_models": 10,
        "receipt_types": 13,
        "timestamp": Utc::now()
    }))
}

async fn list_terminals_handler(State(state): State<AppState>) -> Json<serde_json::Value> {
    let configs: Vec<&TerminalPrinterConfig> = state.printer_configs.values().collect();
    Json(serde_json::json!({
        "terminals": configs,
        "count": configs.len()
    }))
}

async fn get_terminal_handler(
    Path(model_id): Path<String>,
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    match state.printer_configs.get(&model_id) {
        Some(config) => Ok(Json(serde_json::to_value(config).unwrap())),
        None => Err((
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({"error": format!("Terminal model '{}' not found", model_id)})),
        )),
    }
}

async fn print_receipt_handler(
    State(state): State<AppState>,
    Json(req): Json<PrintReceiptRequest>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    match state.engine.render(&req) {
        Ok(receipt) => {
            info!(
                receipt_id = %receipt.receipt_id,
                model_id = %receipt.model_id,
                receipt_type = ?receipt.receipt_type,
                bytes = receipt.byte_count,
                "receipt rendered"
            );
            Ok(Json(serde_json::to_value(ApiResponse::ok(receipt)).unwrap()))
        }
        Err(e) => {
            error!(error = %e, "receipt rendering failed");
            Err((
                StatusCode::UNPROCESSABLE_ENTITY,
                Json(serde_json::json!({"success": false, "error": e})),
            ))
        }
    }
}

async fn test_print_handler(
    Path(model_id): Path<String>,
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<serde_json::Value>)> {
    let req = PrintReceiptRequest {
        terminal_id: "test-terminal".to_string(),
        model_id: model_id.clone(),
        receipt_type: ReceiptType::TestPrint,
        data: ReceiptData {
            merchant_name: Some("54Link Test".to_string()),
            merchant_address: None, merchant_id: None,
            terminal_id: Some(model_id.clone()),
            agent_name: None, agent_id: None,
            transaction_id: None, reference: None, rrn: None, stan: None, auth_code: None,
            card_scheme: None, pan_masked: None, card_holder: None, expiry: None, entry_mode: None,
            currency: None, amount: None, surcharge: None, cashback: None, total_amount: None,
            status: None, response_code: None, response_message: None,
            transaction_date: None, transaction_time: None,
            statement_lines: None, report_period: None, total_transactions: None,
            total_volume: None, successful_txns: None, failed_txns: None, commission_earned: None,
            biller_name: None, account_number: None, service_type: None,
            phone_number: None, network: None, airtime_amount: None,
            footer_message: None,
        },
        copies: Some(1),
        include_qr: Some(false),
    };

    match state.engine.render(&req) {
        Ok(receipt) => Ok(Json(serde_json::to_value(ApiResponse::ok(receipt)).unwrap())),
        Err(e) => Err((
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(serde_json::json!({"success": false, "error": e})),
        )),
    }
}

async fn receipt_types_handler() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "receipt_types": [
            "payment", "refund", "balance_enquiry", "mini_statement",
            "agent_report", "cash_deposit", "cash_withdrawal", "bill_payment",
            "airtime_topup", "transfer_receipt", "pos_settlement", "end_of_day", "test_print"
        ],
        "count": 13
    }))
}

// ── Main ───────────────────────────────────────────────────────────────────────
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".to_string())
        )
        .init();

    let engine = Arc::new(ReceiptEngine::new());
    let printer_configs = Arc::new(get_terminal_printer_configs());

    let state = AppState { engine, printer_configs };

    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/api/v1/printer/terminals", get(list_terminals_handler))
        .route("/api/v1/printer/terminals/:model_id", get(get_terminal_handler))
        .route("/api/v1/printer/terminals/:model_id/test", post(test_print_handler))
        .route("/api/v1/printer/receipt-types", get(receipt_types_handler))
        .route("/api/v1/printer/print", post(print_receipt_handler))
        .with_state(state)
        .layer(tower_http::cors::CorsLayer::permissive())
        .layer(tower_http::trace::TraceLayer::new_for_http());

    let port = std::env::var("PORT").unwrap_or_else(|_| "8097".to_string());
    let addr: SocketAddr = format!("0.0.0.0:{}", port).parse()?;

    info!("rust-pos-printer listening on {}", addr);
    info!("Supported terminals: 10 models (HorizonPay K11/K11 Lite, Newland N910/N910 Pro/N750/ME30SU, PAX A920 MAX/A8900, Topwise T11 Pro/MP45P)");
    info!("Receipt types: 13 templates");

    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener,
        app.into_make_service())
        .await?;

    Ok(())
}

// --- Production: Graceful Shutdown ---
async fn shutdown_signal() {
    let ctrl_c = async {
        tokio::signal::ctrl_c().await.expect("failed to install Ctrl+C handler");
    };
    #[cfg(unix)]
    let terminate = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => { tracing::info!("[shutdown] Received Ctrl+C"); },
        _ = terminate => { tracing::info!("[shutdown] Received SIGTERM"); },
    }
    tracing::info!("[shutdown] Starting graceful shutdown...");
}
