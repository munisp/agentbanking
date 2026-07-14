import express from "express";
import cors from "cors";
import setupRoutes from "./setup/setupRoutes";
import setupBeforeMiddlewares from "./setup/setupBeforeMiddlewares";
import setupAfterMiddlewares from "./setup/setupAfterMiddlewares";

const app = express();

app.use(cors());
app.use(express.json({ limit: "50mb" })); // For JSON payloads
app.use(express.urlencoded({ limit: "50mb", extended: true })); // For form data

setupBeforeMiddlewares(app);
setupRoutes(app);
setupAfterMiddlewares(app);

export default app;
