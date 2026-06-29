import axios, { AxiosError, AxiosInstance } from "axios";
import { readEnv } from "../config/readEnv.config";
import logger from "../config/logger.config";
import {
  CreateBusinessType,
  CreateCustomerType,
  CreateEndUserType,
  GetCollectionFlowUrl,
} from "../types/ballerine";
import { BallerineWorkflow } from "../types/workflow";

/**
 * Encapsulates all ballerine related functionality
 */
class BallerineApiClient {
  private _axiosInstance: AxiosInstance;
  private _baseUrl = readEnv("BALLERINE_API_URL");
  private _apiKey = readEnv("BALLERINE_API_KEY");
  private _logger = logger;

  constructor() {
    this._axiosInstance = axios.create({
      baseURL: this._baseUrl,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Api-Key ${this._apiKey}`,
      },
    });
  }

  /**
   * Creates a ballerine customer for the client.
   * @param payload
   */
  async createCustomer(payload: CreateCustomerType) {
    try {
      this._logger.info("Creating ballerine customer..");

      const response = await this._axiosInstance.post(`/api/v1/internal/customers`, payload);

      console.log(response.data);

      return response.data;
    } catch (e) {
      this._logger.error(`Failed to create ballerine customer: ${e}`);
      throw new Error(`Failed to create ballerine customer: ${e}`);
    }
  }

  /**
   * Creates a ballerine business identity for the business to verify.
   * @param payload
   * @param apiKey
   */
  async createBusiness(payload: CreateBusinessType, apiKey: string) {
    try {
      this._logger.info("Creating ballerine business..");

      const response = await this._axiosInstance.post(`/api/v1/external/businesses`, payload, {
        headers: {
          Authorization: `Api-Key ${apiKey}`,
        },
      });

      this._logger.info("Successfully created ballerine business..");

      return response.data;
    } catch (e: any) {
      this._logger.warn(`Failed to create ballerine business: ${e}`);

      if (e instanceof AxiosError) {
        if (e.response?.status == 409) {
          this._logger.warn("Business already exists, skipping..");
          return;
        }
        throw new Error(`Failed to create ballerine business.`);
      }
    }
  }

  /**
   * Creates a workflow in Ballerine
   * @param workflowDefinitionId - The workflow definition ID
   * @param businessId - The business ID
   * @param context - Additional context data
   * @returns The Ballerine workflow ID
   */
  async createWorkflow(
    workflowId: string,
    context: Record<string, any> = {},
    config: Record<string, any> = {},
    apiKey: string
  ): Promise<BallerineWorkflow> {
    this._logger.info(`Creating Ballerine workflow using definition ${workflowId}`);

    try {
      // Call Ballerine API to create workflow
      const response = await this._axiosInstance.post<BallerineWorkflow>(
        `/api/v1/external/workflows/run`,
        {
          workflowId,
          context,
          config,
        },
        {
          headers: {
            Authorization: `Api-Key ${apiKey}`,
          },
        }
      );

      this._logger.info(`Ballerine workflow created successfully: ${JSON.stringify(response.data)}`);

      return response.data;
    } catch (error) {
      this._logger.error(`Failed to create Ballerine workflow: ${error}`);
      throw new Error(`Failed to create Ballerine workflow: ${error}`);
    }
  }

  /**
   * Creates a ballerine end-user for the contact person.
   * @param payload
   */
  async createEndUser(payload: CreateEndUserType) {
    try {
      this._logger.info("Creating ballerine end user..");

      const response = await this._axiosInstance.post(`/api/v1/external/end-users`, payload);

      this._logger.info(`Create ballerine end user response code: ${response.status}`);
    } catch (e) {
      this._logger.error(e);
      throw new Error("Failed to create ballerine end user.");
    }
  }

  /**
   * Fetch a collection flow url for a running workflow.
   * @param workflowRuntimeId
   * @param apiKey
   * @return token
   */
  async getCollectionFlowUrl(workflowRuntimeDataId: string, apiKey: string): Promise<string> {
    try {
      this._logger.info(`Fetching collection flow url for workflow runtime: ${workflowRuntimeDataId}`);

      const response = await this._axiosInstance.post<GetCollectionFlowUrl>(
        `/api/v1/external/workflows/create-collection-flow-url`,
        { workflowRuntimeDataId },
        {
          headers: {
            Authorization: `Api-Key ${apiKey}`,
          },
        }
      );

      this._logger.info(`Successfully fetched collection flow url: ${JSON.stringify(response.data)}`);

      return response.data.collectionFlowUrl;
    } catch (e: any) {
      this._logger.warn(`Failed to fetch collection flow url: ${e}`);
      throw new Error(`Failed to fetch collection flow url for workflow runtime: ${workflowRuntimeDataId}`);
    }
  }
}

export const ballerineApiClient = new BallerineApiClient();
