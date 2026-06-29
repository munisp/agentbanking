import crypto from "crypto";
import httpStatus from "http-status";
import logger from "../../config/logger.config";
import { AppDataSource } from "../../database/dataSource";
import { ClientEntity } from "../../entity/ClientEntity";
import { ballerineApiClient } from "../../lib/BallerineApiClient";
import { asyncHandler } from "../../middlewares/async";
import { ApiError, raiseHttpError } from "../../middlewares/error";
import { CustomerStatuses } from "../../utils/enums";
import { validateRequest } from "../../validations";
import { PostRegisterClientValidationSchema } from "../../validations/schemas";

export const postRegisterClient = asyncHandler(async (req, res) => {
  try {
    const { clientName, redirectUrls, contact, logo, callBackUrl } =
      validateRequest(PostRegisterClientValidationSchema, req.body);

    const existingClient = await AppDataSource.manager.findOne(ClientEntity, {
      where: {
        client_name: clientName,
      },
    });

    if (existingClient)
      throw new ApiError(
        httpStatus.CONFLICT,
        "Client with the same name already exists.",
        "VER-409-00",
        "verification-service",
      );

    let newClient: ClientEntity | null = null;

    await AppDataSource.manager.transaction(async (manager) => {
      const client = new ClientEntity();

      client.client_name = clientName;
      client.callback_url = callBackUrl;
      client.redirect_urls = redirectUrls;
      client.contact_first_name = contact.firstName;
      client.contact_last_name = contact.lastName;
      client.contact_email = contact.email;
      client.client_id = crypto.randomBytes(16).toString("hex");
      client.client_secret = crypto.randomBytes(24).toString("hex");

      // Should also create a ballerine customer
      const ballerineCustomer = await ballerineApiClient.createCustomer({
        name: clientName,
        displayName: clientName,
        projectName: clientName,
        customerStatus: CustomerStatuses.active,
        logoImageUri: logo || "",
        faviconImageUri: logo || "",
      });

      client.ballerine_customer_id = ballerineCustomer.id;
      client.ballerine_customer_api_key = ballerineCustomer.apiKey;

      newClient = await manager.save(client);
    });

    return res.status(httpStatus.CREATED).json({
      message: "Client created successfully.",
      client: newClient,
    });
  } catch (e: any) {
    logger.error(e);
    const errorMessage = raiseHttpError(
      e.message || "Failed to create client.",
      "POST_REGISTER_CLIENT_ERROR",
    );
    return res
      .status(e.statusCode ?? httpStatus.INTERNAL_SERVER_ERROR)
      .json({ detail: errorMessage });
  }
});
