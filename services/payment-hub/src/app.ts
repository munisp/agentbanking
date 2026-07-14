import express from "express";
import setupRoutes from "./setup/setupRoutes";
import setupBeforeMiddlewares from "./setup/setupBeforeMiddlewares";
import setupAfterMiddlewares from "./setup/setupAfterMiddlewares";
import path from "node:path";

const app = express();

// Serve static files (optional, if you want to serve other assets like CSS/JS)
app.use(express.static(path.join(__dirname, "..", "public")));
app.use(express.json());

setupBeforeMiddlewares(app);
setupRoutes(app);
setupAfterMiddlewares(app);

export default app;
