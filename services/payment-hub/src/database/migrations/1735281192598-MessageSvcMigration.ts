import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1735281192598 implements MigrationInterface {
    name = 'MessageSvcMigration1735281192598'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TYPE "administration"."transaction_status_enum" AS ENUM('success', 'failed', 'pending')`);
        await queryRunner.query(`CREATE TYPE "administration"."transaction_amount_type_enum" AS ENUM('SEND', 'RECEIVE')`);
        await queryRunner.query(`CREATE TYPE "administration"."transaction_currency_enum" AS ENUM('AED', 'AFN', 'ALL', 'AMD', 'ANG', 'AOA', 'ARS', 'AUD', 'AWG', 'AZN', 'BAM', 'BBD', 'BDT', 'BGN', 'BHD', 'BIF', 'BMD', 'BND', 'BOB', 'BRL', 'BSD', 'BTN', 'BWP', 'BYN', 'BZD', 'CAD', 'CDF', 'CHF', 'CLP', 'CNY', 'COP', 'CRC', 'CUC', 'CUP', 'CVE', 'CZK', 'DJF', 'DKK', 'DOP', 'DZD', 'EGP', 'ERN', 'ETB', 'EUR', 'FJD', 'FKP', 'GBP', 'GEL', 'GGP', 'GHS', 'GIP', 'GMD', 'GNF', 'GTQ', 'GYD', 'HKD', 'HNL', 'HRK', 'HTG', 'HUF', 'IDR', 'ILS', 'IMP', 'INR', 'IQD', 'IRR', 'ISK', 'JEP', 'JMD', 'JOD', 'JPY', 'KES', 'KGS', 'KHR', 'KMF', 'KPW', 'KRW', 'KWD', 'KYD', 'KZT', 'LAK', 'LBP', 'LKR', 'LRD', 'LSL', 'LYD', 'MAD', 'MDL', 'MGA', 'MKD', 'MMK', 'MNT', 'MOP', 'MRO', 'MUR', 'MVR', 'MWK', 'MXN', 'MYR', 'MZN', 'NAD', 'NGN', 'NIO', 'NOK', 'NPR', 'NZD', 'OMR', 'PAB', 'PEN', 'PGK', 'PHP', 'PKR', 'PLN', 'PYG', 'QAR', 'RON', 'RSD', 'RUB', 'RWF', 'SAR', 'SBD', 'SCR', 'SDG', 'SEK', 'SGD', 'SHP', 'SLL', 'SOS', 'SPL', 'SRD', 'STD', 'SVC', 'SYP', 'SZL', 'THB', 'TJS', 'TMT', 'TND', 'TOP', 'TRY', 'TTD', 'TVD', 'TWD', 'TZS', 'UAH', 'UGX', 'USD', 'UYU', 'UZS', 'VEF', 'VND', 'VUV', 'WST', 'XAF', 'XCD', 'XDR', 'XOF', 'XPF', 'YER', 'ZAR', 'ZMW', 'ZWD')`);
        await queryRunner.query(`CREATE TYPE "administration"."transaction_quote_status_enum" AS ENUM('abandoned', 'agreed', 'failed', 'in_progress')`);
        await queryRunner.query(`CREATE TYPE "administration"."transaction_transaction_type_enum" AS ENUM('TRANSFER')`);
        await queryRunner.query(`CREATE TABLE "administration"."transaction" ("id" uuid NOT NULL DEFAULT uuid_generate_v4(), "created_at" TIMESTAMP NOT NULL DEFAULT now(), "updated_at" TIMESTAMP NOT NULL DEFAULT now(), "deleted_at" TIMESTAMP, "status" "administration"."transaction_status_enum" NOT NULL DEFAULT 'pending', "completed_at" TIMESTAMP WITH TIME ZONE, "failed_at" TIMESTAMP WITH TIME ZONE, "reason" text, "amount_type" "administration"."transaction_amount_type_enum" NOT NULL, "amount" character varying NOT NULL, "fees" character varying NOT NULL DEFAULT '0.0', "currency" "administration"."transaction_currency_enum" NOT NULL, "quote_id" character varying NOT NULL, "quote_status" "administration"."transaction_quote_status_enum" NOT NULL DEFAULT 'in_progress', "transaction_id" character varying NOT NULL, "ilp_packet" text, "fulfillment" text, "transaction_type" "administration"."transaction_transaction_type_enum" NOT NULL, "payerFsp" character varying NOT NULL, "payeeFsp" character varying NOT NULL, "payer" json NOT NULL, "payee" json NOT NULL, CONSTRAINT "UQ_a468ebb59d3768fbbc1ca070a97" UNIQUE ("quote_id"), CONSTRAINT "PK_89eadb93a89810556e1cbcd6ab9" PRIMARY KEY ("id"))`);
        await queryRunner.query(`CREATE INDEX "IDX_6e02e5a0a6a7400e1c944d1e94" ON "administration"."transaction" ("transaction_id") `);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`DROP INDEX "administration"."IDX_6e02e5a0a6a7400e1c944d1e94"`);
        await queryRunner.query(`DROP TABLE "administration"."transaction"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_transaction_type_enum"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_quote_status_enum"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_currency_enum"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_amount_type_enum"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_status_enum"`);
    }

}
