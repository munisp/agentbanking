import "reflect-metadata";
import setupServer from "./setup/setupServer";
import { tryInitializeDatabase } from "./setup/setupServiceInitializers";

setupServer(tryInitializeDatabase);
