import httpStatus from "http-status";
import createLogger from "../../config/logger.config";
import { readEnv } from "../../config/readEnv.config";
import { asyncHandler } from "../../middlewares/async";
import ApiError from "../../utils/ApiError";
import { extract_name_form_path } from "../../utils/helpers";
import { CreateQuoteSchema, validateRequest } from "../../validations";
import { daprClient, redisClient } from "../../services";
import { IlpPrepare, serializeIlpPrepare } from "ilp-packet";
import { createHash, randomBytes } from "crypto";
import { MojaloopApiClient } from "../../lib/MojaloopApiClient";
import { PubSubTopics, TransactionDirectionEnum } from "../../utils/enums";
import { IQuoteAgreedEvent, IQuoteInitiatedEvent } from "../../types/events";
import { IIlpPrepTxnData } from "../../types";
import { lowerDenominatorMultiplier } from "../../utils/constants";
import Decimal from "decimal.js";

const logger = createLogger(extract_name_form_path(__filename));

const tenant = readEnv("TENANT_NAME", "ucard") as string;

/**
 * Generate ILP Fulfillment and Condition.
 * @param secret The private secret used for generating the fulfillment.
 * @returns Fulfillment and Condition.
 */
function generateFulfillmentAndCondition(secret: Buffer): {
  fulfillment: Buffer;
  condition: Buffer;
} {
  // Generate the fulfillment from the secret
  const fulfillment = createHash("sha256").update(secret).digest();

  // Generate the condition as SHA-256 hash of the fulfillment
  const condition = createHash("sha256").update(fulfillment).digest();

  return { fulfillment, condition };
}

/**
 * Create an ILP Packet, Fulfillment, and Condition for Mojaloop.
 * @param ilpAddress The ILP Address of the Payee.
 * @param amount The amount to be received by the Payee.
 * @param data Transaction details (optional).
 * @returns ILP Packet, Fulfillment, and Condition.
 */
function createIlpPacketWithCondition(
  ilpAddress: string,
  amount: number,
  data: IIlpPrepTxnData
): {
  ilpPacket: string;
  condition: string;
  fulfillment: string;
  secret: string;
} {
  try {
    logger.info(`createIlpPacketWithCondition ${ilpAddress} ${amount}`);
    if (!/^g\.[a-zA-Z0-9._-]+$/.test(ilpAddress)) {
      throw new Error("Invalid ILP address format");
    }

    // Generate a secret for the fulfillment (this is securely stored by the Payee FSP)
    const secret = randomBytes(32);

    // Generate the fulfillment and condition
    const { fulfillment, condition } = generateFulfillmentAndCondition(secret);

    // Create an ILP Prepare packet
    const ilpPrepare: IlpPrepare = {
      amount: amount.toString(),
      executionCondition: condition, // Include the condition in the ILP Packet
      expiresAt: new Date(Date.now() + 15000), // Expiration timestamp (e.g., 15 seconds from now)
      destination: ilpAddress,
      data: Buffer.from(JSON.stringify(data)),
    };

    // Serialize the packet
    const serializedPacket = serializeIlpPrepare(ilpPrepare);

    return {
      ilpPacket: serializedPacket.toString("base64url"),
      secret: secret.toString("base64url"),
      condition: condition.toString("base64url"),
      fulfillment: fulfillment.toString("base64url"),
    };
  } catch (error) {
    logger.error("error creating Ilp-packet", error);
    throw error;
  }
}

// payee recieves a quote request from payer fsp
// quote is calculated and persisted
export const create_quote = asyncHandler(async (req, res) => {
  logger.info("create_quote");

  const source = req.headers["fspiop-source"] as string;
  const destination = req.headers["fspiop-destination"] as string | undefined;

  logger.info(`create_quote source: ${source} destination: ${destination} tenant: ${tenant}`);

  if (tenant !== destination) {
    throw new ApiError(httpStatus.BAD_REQUEST, "The incoming quote request is invalid");
  }

  logger.info(`Body: ${JSON.stringify(req.body)}`);

  const payload = validateRequest(CreateQuoteSchema, req.body);

  const identifier = payload.payee.partyIdInfo.partyIdentifier.replace(/^\+/, "");

  // Generate ilpPacket
  const ilpAddress = `g.ng.tipnet.${tenant}.${payload.payee.partyIdInfo.partyIdType}.${identifier}`;
  logger.info(`ilpAddress: ${ilpAddress}`);

  const transactionDetails: IIlpPrepTxnData = {
    note: payload.note,
    transactionId: payload.transactionId,
    currency: payload.amount.currency,
  };

  const amount = new Decimal(payload.amount.amount)
    .times(lowerDenominatorMultiplier[payload.amount.currency])
    .toDecimalPlaces(0, Decimal.ROUND_HALF_UP);

  const { ilpPacket, condition, fulfillment, secret } = createIlpPacketWithCondition(
    ilpAddress,
    Number(amount),
    transactionDetails
  );

  logger.info(`ilpPacket ${ilpPacket}`);
  logger.info(`condition: ${condition}`);
  logger.info(`fulfillment: ${fulfillment}`);

  const expiration = new Date();
  expiration.setSeconds(expiration.getSeconds() + 15); // Expire 15 seconds after initiation

  const quotePersistKey = `quote:payee:${payload.transactionId}`;

  const response = {
    ilpPacket,
    condition,
    transferAmount: payload.amount,
    expiration: expiration.toISOString(),
  };

  logger.info(`Quote Response ${JSON.stringify(response)}`);

  await Promise.all([
    redisClient.set(
      quotePersistKey,
      JSON.stringify({
        fulfillment,
        ilpAddress,
        amount: amount.toString(),
      }),
      "EX",
      20
    ),
    MojaloopApiClient.getInstance().send_quote_res(payload.quoteId, tenant, source, response),
    daprClient.publishTxnNotification<IQuoteInitiatedEvent>(PubSubTopics.quote_initiated, {
      amount: payload.amount,
      destinationFsp: destination,
      sourceFsp: source,
      quote_id: payload.quoteId,
      transaction_id: payload.transactionId,
      transaction_type: payload.transactionType.scenario,
      amount_type: payload.amountType,
      fulfillment,
      fulfilment_secret: secret,
      payee: {
        idType: payload.payee.partyIdInfo.partyIdType,
        idValue: payload.payee.partyIdInfo.partyIdentifier,
      },
      payer: {
        idType: payload.payer.partyIdInfo.partyIdType,
        idValue: payload.payer.partyIdInfo.partyIdentifier,
      },
      transaction_direction: TransactionDirectionEnum.incoming,
      tenant,
    }),
    daprClient.publishTxnNotification<IQuoteAgreedEvent>(PubSubTopics.quote_agreed, {
      quote_id: payload.quoteId,
    }),
  ]);

  res.status(httpStatus.OK).send();
});
