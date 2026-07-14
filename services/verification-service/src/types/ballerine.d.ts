import { CustomerStatuses } from "../utils/enums";

export type CreateEndUserType = {
  firstName: string;
  lastName: string;
  email: string;
  isContactPerson: boolean;
  correlationId: string;
};

export type CreateCustomerType = {
  name: string;
  displayName: string;
  customerStatus: CustomerStatuses;
  logoImageUri: string;
  faviconImageUri: string;
  projectName: string;
};

export type CreateBusinessType = {
  companyName: string;
  registrationNumber: string;
  correlationId: string;
  mccCode: string;
  businessType: string;
  address: {
    country: string;
    countryCode: string;
    city: string;
    street: string;
    postcode: string;
    state: string;
  };
};

export type GetCollectionFlowUrl = {
  collectionFlowUrl: string;
};
