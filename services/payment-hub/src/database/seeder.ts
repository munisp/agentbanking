import { AppDataSource } from "./dataSource";
import { TenantSeeder } from "./seeders";

// Parse arguments
const args = process.argv.slice(2);
const forceSeed = args.includes("-f");

AppDataSource.initialize()
  .then(async () => {
    await new TenantSeeder().seed(AppDataSource, forceSeed);
    await AppDataSource.destroy();
  })
  .catch((error) => console.log("Error seeding database:", error));
