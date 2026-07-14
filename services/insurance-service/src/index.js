const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");

const app = express();
const PORT = process.env.PORT || 3023;

app.use(helmet());
app.use(cors());
app.use(morgan("combined"));
app.use(express.json());

app.get("/health", (req, res) => res.json({ status: "ok", service: "insurance-service" }));

// Products catalogue
app.get("/api/v1/products", (req, res) => {
  res.json({
    products: [
      { id: "INS-001", name: "Float Protect", type: "float", premium_monthly: 500, coverage: 200000, active: true },
      { id: "INS-002", name: "Device Cover", type: "device", premium_monthly: 300, coverage: 150000, active: true },
      { id: "INS-003", name: "Health Basic", type: "health", premium_monthly: 1500, coverage: 500000, active: true },
      { id: "INS-004", name: "Income Protection", type: "income", premium_monthly: 800, coverage: 250000, active: true },
      { id: "INS-005", name: "Funeral Cover", type: "life", premium_monthly: 200, coverage: 100000, active: true },
    ]
  });
});

// Agent policies
app.get("/api/v1/policies", (req, res) => {
  res.json({ policies: [] });
});

app.post("/api/v1/policies/enroll", (req, res) => {
  res.status(201).json({
    policy: {
      id: `POL-${Date.now()}`,
      agent_id: req.body.agent_id,
      product_id: req.body.product_id,
      status: "active",
      start_date: new Date().toISOString(),
      next_deduction: new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString(),
    }
  });
});

// Micro-insurance policies
app.get("/api/v1/micro/policies", (req, res) => {
  const agentId = req.query.agent_id;
  res.json({
    policies: [],
    agent_id: agentId,
    total: 0,
  });
});

// Float insurance claims
app.get("/api/v1/float-claims", (req, res) => {
  const agentId = req.query.agent_id;
  res.json({ claims: [], agent_id: agentId, total: 0 });
});

app.get("/api/v1/float-claims/stats", (req, res) => {
  const agentId = req.query.agent_id;
  res.json({
    agent_id: agentId,
    total_claims: 0,
    approved: 0,
    pending: 0,
    rejected: 0,
    total_payout: 0,
  });
});

app.post("/api/v1/float-claims", (req, res) => {
  res.status(201).json({
    claim: {
      id: `CLM-${Date.now()}`,
      ...req.body,
      status: "pending",
      submitted_at: new Date().toISOString(),
    }
  });
});

app.patch("/api/v1/float-claims/:id/status", (req, res) => {
  res.json({ success: true, id: req.params.id, status: req.body.status });
});

// Payment processing integration
app.post("/api/v1/payments/deduct", (req, res) => {
  res.json({ success: true, deducted: req.body.amount, transaction_ref: `INS-TXN-${Date.now()}` });
});

app.listen(PORT, () => console.log(`insurance-service running on port ${PORT}`));
