const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");

const app = express();
const PORT = process.env.PORT || 3020;

app.use(helmet());
app.use(cors());
app.use(morgan("combined"));
app.use(express.json());

// Health check
app.get("/health", (req, res) => res.json({ status: "ok", service: "merchant-service" }));

// Merchant CRUD
app.get("/merchant/api/v1/merchants", (req, res) => {
  res.json({ merchants: [], page: 1, total: 0 });
});

app.get("/merchant/api/v1/merchants/:id", (req, res) => {
  res.json({ merchant: { id: req.params.id } });
});

app.post("/merchant/api/v1/merchants", (req, res) => {
  res.status(201).json({ merchant: { id: `MCH-${Date.now()}`, ...req.body, status: "pending", created_at: new Date().toISOString() } });
});

app.patch("/merchant/api/v1/merchants/:id/status", (req, res) => {
  res.json({ success: true, id: req.params.id, status: req.body.status });
});

app.get("/merchant/api/v1/merchants/:id/transactions", (req, res) => {
  res.json({ transactions: [] });
});

app.get("/merchant/api/v1/merchants/:id/analytics", (req, res) => {
  res.json({ analytics: { total_volume: 0, transaction_count: 0, avg_ticket: 0 } });
});

// KYC
app.post("/merchant/api/v1/merchants/:id/kyc", (req, res) => {
  res.json({ success: true, kyc_status: "under_review" });
});

app.listen(PORT, () => console.log(`merchant-service running on port ${PORT}`));
