import { MigrationInterface, QueryRunner } from "typeorm";

export class AddMissingFeatureFlagEnumValues1748686800000
  implements MigrationInterface
{
  public transaction = false;

  public async up(queryRunner: QueryRunner): Promise<void> {
    const missingValues = [
      "cooperative_management",
      "diaspora_banking",
      "trade_finance",
      "securities_trading",
      "temporal_access",
      "gamification",
      "salary_processing",
    ];

    const enumTypes = [
      "tenant_feature_flag_name_enum",
      "tenant_branch_feature_flag_name_enum",
    ];

    for (const enumType of enumTypes) {
      for (const value of missingValues) {
        await queryRunner.query(
          `DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = '${enumType}')
            AND NOT EXISTS (
              SELECT 1 FROM pg_enum
              JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
              WHERE pg_type.typname = '${enumType}'
              AND pg_enum.enumlabel = '${value}'
            ) THEN
              ALTER TYPE ${enumType} ADD VALUE '${value}';
            END IF;
          END $$;`
        );
      }
    }
  }

  public async down(_queryRunner: QueryRunner): Promise<void> {
    // PostgreSQL does not support removing enum values without recreating the type
  }
}
