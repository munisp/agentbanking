import { AppDataSource } from "../database/dataSource";
import { AppConfigEntity } from "../entity/AppConfigEntity";

/**
 * Retrieve app config for a given key
 * @param key
 * @returns
 */
export async function getAppConfig(key: string) {
  const appConfig = await AppDataSource.manager.findOne(AppConfigEntity, {
    where: {
      key,
    },
  });

  if (!appConfig) throw new Error("App config not found.");

  return appConfig.value;
}
