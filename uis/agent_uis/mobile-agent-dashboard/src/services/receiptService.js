import * as Print from "expo-print";
import { useTheme } from 'react-native-paper';
import * as Sharing from "expo-sharing";
// ── HTML templates ────────────────────────────────────────────────────────────

const BASE_CSS = `
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Courier New', Courier, monospace;
    font-size: 12px;
    color: #111;
    background: #fff;
    max-width: 380px;
    margin: 0 auto;
    padding: 20px 16px;
  }
  .center { text-align: center; }
  .brand { font-size: 22px; font-weight: 900; letter-spacing: 4px; }
  .sub { font-size: 10px; color: #666; margin-top: 2px; }
  .dash { border: none; border-top: 1px dashed #bbb; margin: 10px 0; }
  .row { display: flex; justify-content: space-between; padding: 3px 0; }
  .lbl { color: #555; }
  .val { font-weight: bold; max-width: 60%; text-align: right; word-break: break-all; }
  .amount-box {
    text-align: center; padding: 10px 0;
    font-size: 26px; font-weight: 900; color: colors.primary;
  }
  .status-ok { text-align: center; color: #10B981; font-weight: bold; font-size: 13px; }
  .footer { text-align: center; color: #aaa; font-size: 10px; margin-top: 16px; line-height: 1.6; }
  .section-title { font-size: 10px; text-transform: uppercase; color: #888; margin-bottom: 4px; letter-spacing: 1px; }
`;

function formatNGN(amount) {
  const { colors } = useTheme();

  return `NGN ${Number(amount || 0).toLocaleString("en-NG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatDateLong(dateVal) {
  return new Date(dateVal || Date.now()).toLocaleString("en-NG", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function buildTransactionReceiptHTML(txn) {
  const maskedCard = txn.cardNumber
    ? `**** **** **** ${String(txn.cardNumber).slice(-4)}`
    : null;

  return `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${BASE_CSS}</style></head>
<body>
  <div class="center">
    <div class="brand">54agent</div>
    <div class="sub">Agent Banking Services</div>
  </div>
  <hr class="dash">
  <div class="center">
    <div class="section-title">Transaction Receipt</div>
    <div class="amount-box">${formatNGN(txn.amount)}</div>
    <div class="status-ok">✓ ${txn.type === "cashout" ? "WITHDRAWAL SUCCESSFUL" : txn.type === "cashin" ? "DEPOSIT SUCCESSFUL" : "TRANSFER SUCCESSFUL"}</div>
  </div>
  <hr class="dash">
  <div class="row"><span class="lbl">Date</span><span class="val">${formatDateLong(txn.timestamp)}</span></div>
  <div class="row"><span class="lbl">Reference</span><span class="val">${txn.reference || "N/A"}</span></div>
  ${txn.description ? `<div class="row"><span class="lbl">Description</span><span class="val">${txn.description}</span></div>` : ""}
  ${maskedCard ? `<div class="row"><span class="lbl">Card</span><span class="val">${maskedCard}${txn.cardProvider ? ` (${txn.cardProvider})` : ""}</span></div>` : ""}
  ${txn.accountType ? `<div class="row"><span class="lbl">Account Type</span><span class="val">${txn.accountType}</span></div>` : ""}
  <hr class="dash">
  <div class="row"><span class="lbl">Agent</span><span class="val">${txn.agentName || "Agent"}</span></div>
  ${txn.agentId ? `<div class="row"><span class="lbl">Agent ID</span><span class="val">${txn.agentId}</span></div>` : ""}
  <hr class="dash">
  <div class="footer">
    Thank you for using 54agent.<br>
    Keep this receipt for your records.<br>
    For support: support@54agent.com
  </div>
</body>
</html>`;
}

export function buildOrderReceiptHTML(order) {
  const itemsHTML = (order.items || [])
    .map(
      (item) => `
      <div class="row">
        <span class="lbl">${item.item_name} ×${item.quantity}</span>
        <span class="val">${formatNGN(item.subtotal)}</span>
      </div>`,
    )
    .join("");

  return `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${BASE_CSS}</style></head>
<body>
  <div class="center">
    <div class="brand">${(order.store_name || "54agent").toUpperCase()}</div>
    <div class="sub">Order Receipt</div>
    <div style="margin-top:6px;font-size:11px;color:#555;">${formatDateLong(order.created_at)}</div>
  </div>
  <hr class="dash">
  ${order.customer_name ? `
  <div class="section-title">Customer</div>
  <div class="row"><span class="lbl">Name</span><span class="val">${order.customer_name}</span></div>
  ${order.customer_phone ? `<div class="row"><span class="lbl">Phone</span><span class="val">${order.customer_phone}</span></div>` : ""}
  <hr class="dash">` : ""}
  <div class="section-title">Items</div>
  ${itemsHTML}
  <hr class="dash">
  <div class="row"><span class="lbl">Subtotal</span><span class="val">${formatNGN(order.subtotal)}</span></div>
  <div class="row"><span class="lbl">Tax (7.5%)</span><span class="val">${formatNGN(order.tax)}</span></div>
  <hr class="dash">
  <div class="row" style="font-size:15px;font-weight:900;">
    <span>TOTAL</span><span style="color:colors.primary;">${formatNGN(order.total)}</span>
  </div>
  <hr class="dash">
  <div class="row"><span class="lbl">Payment</span><span class="val">${(order.payment_method || "CASH").toUpperCase()}</span></div>
  <div class="row"><span class="lbl">Order #</span><span class="val">${order.id || "N/A"}</span></div>
  <hr class="dash">
  <div class="footer">
    Thank you for your business!<br>
    Served by: ${order.created_by || "Agent"}<br>
    Powered by 54agent
  </div>
</body>
</html>`;
}

// ── Print & share ─────────────────────────────────────────────────────────────

export async function printHTML(html) {
  await Print.printAsync({ html });
}

export async function shareHTMLAsPDF(html, filename = "receipt.pdf") {
  const { uri } = await Print.printToFileAsync({ html, base64: false });
  const canShare = await Sharing.isAvailableAsync();
  if (!canShare) throw new Error("Sharing is not available on this device.");
  await Sharing.shareAsync(uri, {
    mimeType: "application/pdf",
    dialogTitle: "Share Receipt",
    UTI: "com.adobe.pdf",
  });
}

export async function printTransactionReceipt(txn) {
  await printHTML(buildTransactionReceiptHTML(txn));
}

export async function shareTransactionReceipt(txn) {
  await shareHTMLAsPDF(
    buildTransactionReceiptHTML(txn),
    `receipt-${txn.reference || Date.now()}.pdf`,
  );
}

export async function printOrderReceipt(order) {
  await printHTML(buildOrderReceiptHTML(order));
}

export async function shareOrderReceipt(order) {
  await shareHTMLAsPDF(
    buildOrderReceiptHTML(order),
    `order-${order.id || Date.now()}.pdf`,
  );
}
