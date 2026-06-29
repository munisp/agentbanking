import express from "express";

const router = express.Router();

router.get("/health", (_, res) => {
  return res.status(200).send("API is healthy");
});

export default router;
