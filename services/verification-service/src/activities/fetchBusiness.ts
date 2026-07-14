import * as z from "zod";
import { PostInitializeVerificationValidationSchema } from "../validations/schemas";
import logger from "../config/logger.config";
import { AppDataSource } from "../database/dataSource";
import { BusinessEntity } from "../entity/BusinessEntity";
import { ballerineApiClient } from "../lib/BallerineApiClient";
import { LocationEntity } from "../entity/LocationEntity";
import { ClientEntity } from "../entity/ClientEntity";

/**
 * Retreive a business identity, creates one if it doesn't exist.
 * @param payload
 * @param client
 * @returns BusinessEntity.
 */
export async function fetchBusiness(
  payload: z.infer<typeof PostInitializeVerificationValidationSchema>,
  client: ClientEntity
): Promise<BusinessEntity> {
  logger.info(`Check if business ${payload.companyName} already exists..`);

  let business = await AppDataSource.manager.findOne(BusinessEntity, {
    where: [
      { company_name: payload.companyName },
      { registration_number: payload.registrationNumber },
      { mcc_code: payload.mccCode },
    ],
  });

  if (business) {
    logger.info(`Business ${payload.companyName} already exists, skipping creation..`);
  } else {
    logger.info(`Business ${payload.companyName} does not exist, creating..`);

    const ballerineBusiness = await ballerineApiClient.createBusiness(
      {
        ...payload,
        correlationId: client.client_id + "-" + payload.companyName,
      },
      client.ballerine_customer_api_key
    );

    logger.info("Creating local business identity..");

    const location = new LocationEntity();
    location.country = payload.address.country;
    location.country_code = payload.address.countryCode;
    location.city = payload.address.city;
    location.post_code = payload.address.postcode;
    location.state = payload.address.state;
    location.street = payload.address.street;
    await AppDataSource.manager.save(location);

    business = new BusinessEntity();
    business.ballerine_business_id = ballerineBusiness.id;
    business.company_name = payload.companyName;
    business.business_type = payload.businessType;
    business.registration_number = payload.registrationNumber;
    business.mcc_code = payload.mccCode;
    business.contact_name = payload.contact.firstName + " " + payload.contact.lastName;
    business.contact_email = payload.contact.email;
    business.location = location;
    await AppDataSource.manager.save(business);
  }

  return business;
}
