import { AppDataSource } from "../database/dataSource";
import { TenantBrandingEntity } from "../entity/TenantBrandingEntity";
import { TenantContactEntity } from "../entity/TenantContactEntity";
import { TenantEntity } from "../entity/TenantEntity";
import { TenantFeatureFlagEntity } from "../entity/TenantFeatureFlagEntity";
import {
  ICreateTenantBranchPayload,
  ICreateTenantPayload,
  IUpdateTenantBranchPayload,
  IUpdateTenantPayload,
} from "../types/tenant";
import { hashString } from "../utils";
import { TenantStatus } from "../utils/enums";
import { TenantBranchEntity } from "../entity/TenantBranchEntity";
import { TenantBranchContactEntity } from "../entity/TenantBranchContactEntity";
import { TenantBranchFeatureFlagEntity } from "../entity/TenantBranchFeatureFlagEntity";
import logger from "../config/logger.config";
import { billingService } from "../services/billingService";

export class TenantRepository {
  private entity = TenantEntity;
  private manager = AppDataSource.manager;

  constructor() {}

  async createTenant(payload: ICreateTenantPayload) {
    return AppDataSource.transaction(async (manager) => {
      const existingTenant = await manager.findOne(this.entity, {
        where: { tenant_id: payload.tenantId },
      });

      if (existingTenant) throw new Error("Tenant already exists.");

      // Create contact
      const contact = new TenantContactEntity();
      contact.name = payload.contact.name;
      contact.email = payload.contact.email;
      contact.phone = payload.contact.phone;
      await manager.save(contact);

      // Create branding
      let branding: TenantBrandingEntity | null = null;
      if (payload.branding) {
        branding = new TenantBrandingEntity();
        branding.domain = payload.branding.domain;
        branding.logo_url = payload.branding.logoUrl;
        branding.favicon_url = payload.branding.faviconUrl;
        branding.primary_color = payload.branding.primaryColor;
        branding.secondary_color = payload.branding.secondaryColor;
        await manager.save(branding);
      }

      // Create feature flags
      const featureFlags = payload.features.map((feature) => {
        const featureFlag = new TenantFeatureFlagEntity();
        featureFlag.name = feature.flag;
        featureFlag.is_enabled = true;
        featureFlag.config = feature.config;
        return featureFlag;
      });
      await manager.save(featureFlags);

      // Create tenant
      const tenant = new this.entity();
      tenant.name = payload.name;
      tenant.type = payload.type;
      tenant.cac_certificate_url = payload.cacCertificateUrl;
      tenant.cbn_license_url = payload.cbnLicenseUrl;
      tenant.status = TenantStatus.ACTIVE;
      tenant.contact = contact;
      tenant.feature_flags = featureFlags;
      tenant.tenant_id = payload.tenantId;
      tenant.tenant_secret = await hashString(`tenant-${payload.tenantId}-${Date.now()}`);
      tenant.branding = branding ?? undefined;
      tenant.api_configuration = payload.apiConfiguration;
      await manager.save(tenant);

      return tenant;
    });
  }

  async updateTenant(tenantId: string, payload: IUpdateTenantPayload) {
    return AppDataSource.transaction(async (manager) => {
      const tenant = await manager.findOne(this.entity, {
        where: { tenant_id: tenantId },
        relations: {
          contact: true,
          branding: true,
          feature_flags: true,
        },
      });

      if (!tenant) throw new Error("Tenant not found.");

      /* -------------------- Tenant fields -------------------- */
      if (payload.name) tenant.name = payload.name;
      if (payload.type) tenant.type = payload.type;
      if (payload.cacCertificateUrl) tenant.cac_certificate_url = payload.cacCertificateUrl;
      if (payload.cbnLicenseUrl) tenant.cbn_license_url = payload.cbnLicenseUrl;
      if (payload.apiConfiguration) tenant.api_configuration = payload.apiConfiguration;

      await manager.save(tenant);

      /* -------------------- Contact -------------------- */
      if (payload.contact) {
        tenant.contact ??= new TenantContactEntity();

        if (payload.contact.name) tenant.contact.name = payload.contact.name;
        if (payload.contact.email) tenant.contact.email = payload.contact.email;
        if (payload.contact.phone) tenant.contact.phone = payload.contact.phone;

        await manager.save(tenant.contact);
      }

      /* -------------------- Branding -------------------- */
      if (payload.branding) {
        tenant.branding ??= new TenantBrandingEntity();

        if (payload.branding.domain) tenant.branding.domain = payload.branding.domain;
        if (payload.branding.logoUrl) tenant.branding.logo_url = payload.branding.logoUrl;
        if (payload.branding.faviconUrl) tenant.branding.favicon_url = payload.branding.faviconUrl;
        if (payload.branding.primaryColor) tenant.branding.primary_color = payload.branding.primaryColor;
        if (payload.branding.secondaryColor)
          tenant.branding.secondary_color = payload.branding.secondaryColor;

        await manager.save(tenant.branding);
      }

      /* -------------------- Feature flags -------------------- */
      if (payload.features?.length) {
        const existing = new Map(tenant.feature_flags.map((f) => [f.name, f]));

        const flags = payload.features.map((feature) => {
          let flag = existing.get(feature.flag);

          if (!flag) {
            flag = new TenantFeatureFlagEntity();
            flag.name = feature.flag;
          }

          flag.is_enabled = true;
          if (feature.config) flag.config = feature.config;

          return flag;
        });

        tenant.feature_flags = await manager.save(flags);
      }

      await manager.save(tenant);

      return tenant;
    });
  }

  async suspendTenant(tenant_id: string) {
    const tenant = await this.manager.findOne(this.entity, {
      where: {
        tenant_id,
      },
    });

    if (!tenant) throw new Error("Tenant not found.");

    tenant.status = TenantStatus.SUSPENDED;

    await this.manager.save(tenant);
  }

  async unSuspendTenant(tenant_id: string) {
    const tenant = await this.manager.findOne(this.entity, {
      where: {
        tenant_id,
      },
    });

    if (!tenant) throw new Error("Tenant not found.");

    tenant.status = TenantStatus.ACTIVE;

    await this.manager.save(tenant);
  }

  async findOne(tenant_id: string) {
    return await this.manager.findOne(this.entity, {
      where: {
        tenant_id,
      },
    });
  }

  async findAll() {
    return await this.manager.find(this.entity, {
      order: {
        created_at: "DESC",
      },
    });
  }

  async getFeatures(tenant_id: string) {
    return await this.manager.find(TenantFeatureFlagEntity, {
      where: {
        tenant: {
          tenant_id: tenant_id,
        },
      },
    });
  }

  async createBranch(tenant_id: string, payload: ICreateTenantBranchPayload) {
    await AppDataSource.transaction(async (manager) => {
      const existing = await manager.findOne(TenantBranchEntity, {
        where: {
          code: payload.code,
          name: payload.name,
          tenant_id: tenant_id,
        },
      });

      if (existing) throw new Error("Branch name or code already exists.");

      // Create contact
      const contact = new TenantBranchContactEntity();
      contact.name = payload.contact.name;
      contact.email = payload.contact.email;
      contact.phone = payload.contact.phone;
      await manager.save(contact);

      // Create feature flags
      const featureFlags = payload.features.map((feature) => {
        const featureFlag = new TenantBranchFeatureFlagEntity();
        featureFlag.name = feature.flag;
        featureFlag.is_enabled = true;
        featureFlag.config = feature.config;
        return featureFlag;
      });
      await manager.save(featureFlags);

      const branch = new TenantBranchEntity();
      branch.name = payload.name;
      branch.code = payload.code;
      branch.webhook_url = payload.webhookUrl;
      branch.callback_url = payload.callbackUrl;
      branch.location = payload.location;
      branch.contact = contact;
      branch.feature_flags = featureFlags;
      branch.tenant_id = tenant_id;
      await manager.save(branch);
    });
  }

  async updateBranch(tenant_id: string, branchId: number, payload: IUpdateTenantBranchPayload) {
    return AppDataSource.transaction(async (manager) => {
      const branch = await manager.findOne(TenantBranchEntity, {
        where: {
          id: branchId,
          tenant_id,
        },
        relations: {
          contact: true,
          feature_flags: true,
        },
      });

      if (!branch) throw new Error("Branch not found.");

      /* -------------------- Uniqueness check (optional fields) -------------------- */
      if (payload.name || payload.code) {
        const existing = await manager.findOne(TenantBranchEntity, {
          where: {
            tenant_id,
            name: payload.name ?? branch.name,
            code: payload.code ?? branch.code,
          },
        });

        if (existing && existing.id !== branch.id) {
          throw new Error("Branch name or code already exists.");
        }
      }

      /* -------------------- Branch fields -------------------- */
      if (payload.name) branch.name = payload.name;
      if (payload.code) branch.code = payload.code;
      if (payload.webhookUrl) branch.webhook_url = payload.webhookUrl;
      if (payload.callbackUrl) branch.callback_url = payload.callbackUrl;
      if (payload.location) branch.location = payload.location;

      /* -------------------- Contact -------------------- */
      if (payload.contact) {
        branch.contact ??= new TenantBranchContactEntity();

        if (payload.contact.name) branch.contact.name = payload.contact.name;
        if (payload.contact.email) branch.contact.email = payload.contact.email;
        if (payload.contact.phone) branch.contact.phone = payload.contact.phone;

        await manager.save(branch.contact);
      }

      /* -------------------- Feature flags -------------------- */
      if (payload.features?.length) {
        const existingFlags = new Map(branch.feature_flags.map((f) => [f.name, f]));

        const flags = payload.features.map((feature) => {
          let flag = existingFlags.get(feature.flag);

          if (!flag) {
            flag = new TenantBranchFeatureFlagEntity();
            flag.name = feature.flag;
          }

          flag.is_enabled = true;
          if (feature.config) flag.config = feature.config;

          return flag;
        });

        branch.feature_flags = await manager.save(flags);
      }

      await manager.save(branch);
      return branch;
    });
  }

  async getBranches(tenant_id: string) {
    return await this.manager.find(TenantBranchEntity, {
      where: {
        tenant_id,
      },
      relations: ["contact", "feature_flags"],
      order: {
        created_at: "DESC",
      },
    });
  }

  async suspendBranch(tenantId: string, branchId: number) {
    const branch = await this.manager.findOne(TenantBranchEntity, {
      where: {
        id: branchId,
        tenant_id: tenantId,
      },
    });

    if (!branch) throw new Error("Branch not found.");

    branch.status = TenantStatus.SUSPENDED;

    await this.manager.save(branch);
  }

  async unSuspendBranch(tenantId: string, branchId: number) {
    const branch = await this.manager.findOne(TenantBranchEntity, {
      where: {
        id: branchId,
        tenant_id: tenantId,
      },
    });

    if (!branch) throw new Error("Branch not found.");

    branch.status = TenantStatus.ACTIVE;

    await this.manager.save(branch);
  }

  async createBillingProfile(tenantId: string, plan: string) {
    return await billingService.createBillingProfile(tenantId, plan);
  }
}

export const tenantRepository = new TenantRepository();
