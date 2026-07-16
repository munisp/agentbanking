import { MigrationInterface, QueryRunner } from "typeorm";

export class MessageSvcMigration1735662682188 implements MigrationInterface {
    name = 'MessageSvcMigration1735662682188'

    public async up(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ADD "local_transaction_id" character varying`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum" RENAME TO "transaction_currency_enum_old"`);
        await queryRunner.query(`CREATE TYPE "administration"."transaction_currency_enum" AS ENUM('NGN')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "currency" TYPE "administration"."transaction_currency_enum" USING "currency"::"text"::"administration"."transaction_currency_enum"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_currency_enum_old"`);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        await queryRunner.query(`CREATE TYPE "administration"."transaction_currency_enum_old" AS ENUM('AED', 'AFN', 'ALL', 'AMD', 'ANG', 'AOA', 'ARS', 'AUD', 'AWG', 'AZN', 'BAM', 'BBD', 'BDT', 'BGN', 'BHD', 'BIF', 'BMD', 'BND', 'BOB', 'BRL', 'BSD', 'BTN', 'BWP', 'BYN', 'BZD', 'CAD', 'CDF', 'CHF', 'CLP', 'CNY', 'COP', 'CRC', 'CUC', 'CUP', 'CVE', 'CZK', 'DJF', 'DKK', 'DOP', 'DZD', 'EGP', 'ERN', 'ETB', 'EUR', 'FJD', 'FKP', 'GBP', 'GEL', 'GGP', 'GHS', 'GIP', 'GMD', 'GNF', 'GTQ', 'GYD', 'HKD', 'HNL', 'HRK', 'HTG', 'HUF', 'IDR', 'ILS', 'IMP', 'INR', 'IQD', 'IRR', 'ISK', 'JEP', 'JMD', 'JOD', 'JPY', 'KES', 'KGS', 'KHR', 'KMF', 'KPW', 'KRW', 'KWD', 'KYD', 'KZT', 'LAK', 'LBP', 'LKR', 'LRD', 'LSL', 'LYD', 'MAD', 'MDL', 'MGA', 'MKD', 'MMK', 'MNT', 'MOP', 'MRO', 'MUR', 'MVR', 'MWK', 'MXN', 'MYR', 'MZN', 'NAD', 'NGN', 'NIO', 'NOK', 'NPR', 'NZD', 'OMR', 'PAB', 'PEN', 'PGK', 'PHP', 'PKR', 'PLN', 'PYG', 'QAR', 'RON', 'RSD', 'RUB', 'RWF', 'SAR', 'SBD', 'SCR', 'SDG', 'SEK', 'SGD', 'SHP', 'SLL', 'SOS', 'SPL', 'SRD', 'STD', 'SVC', 'SYP', 'SZL', 'THB', 'TJS', 'TMT', 'TND', 'TOP', 'TRY', 'TTD', 'TVD', 'TWD', 'TZS', 'UAH', 'UGX', 'USD', 'UYU', 'UZS', 'VEF', 'VND', 'VUV', 'WST', 'XAF', 'XCD', 'XDR', 'XOF', 'XPF', 'YER', 'ZAR', 'ZMW', 'ZWD')`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" ALTER COLUMN "currency" TYPE "administration"."transaction_currency_enum_old" USING "currency"::"text"::"administration"."transaction_currency_enum_old"`);
        await queryRunner.query(`DROP TYPE "administration"."transaction_currency_enum"`);
        await queryRunner.query(`ALTER TYPE "administration"."transaction_currency_enum_old" RENAME TO "transaction_currency_enum"`);
        await queryRunner.query(`ALTER TABLE "administration"."transaction" DROP COLUMN "local_transaction_id"`);
    }

}
