const express = require("express");
const cors = require("cors");
const helmet = require("helmet");
const morgan = require("morgan");

const app = express();
const PORT = process.env.PORT || 3021;

app.use(helmet());
app.use(cors());
app.use(morgan("combined"));
app.use(express.json());

app.get("/health", (req, res) => res.json({ status: "ok", service: "gdpr-service" }));

// Data Subject Requests
app.get("/api/v1/requests", (req, res) => {
  res.json({ requests: [], total: 0 });
});

app.post("/api/v1/requests", (req, res) => {
  res.status(201).json({
    request: { id: `gdpr-${Date.now()}`, ...req.body, status: "pending", created_at: new Date().toISOString() }
  });
});

app.patch("/api/v1/requests/:id", (req, res) => {
  res.json({ success: true, id: req.params.id, ...req.body });
});

app.post("/api/v1/requests/:id/export", async (req, res) => {
  res.json({ success: true, message: "Export queued. Download link will be emailed." });
});

app.post("/api/v1/requests/:id/erase", async (req, res) => {
  res.json({ success: true, message: "Erasure request queued." });
});

// Consent management
app.get("/api/v1/consents/:subject_id", (req, res) => {
  res.json({ consents: [] });
});

app.post("/api/v1/consents", (req, res) => {
  res.status(201).json({ consent: { id: `con-${Date.now()}`, ...req.body } });
});

app.listen(PORT, () => console.log(`gdpr-service running on port ${PORT}`));
