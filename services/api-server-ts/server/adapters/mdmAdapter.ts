/**
 * MDM Compliance Engine Adapter (S88-04)
 * Bridges Node.js to Go mdm-compliance-engine for device management
 */
import { mdmComplianceEngine, type AdapterResponse } from "./goServiceAdapter";

export interface DeviceCheckResult {
  deviceId: string;
  compliant: boolean;
  violations: string[];
  lastChecked: string;
  riskScore: number;
}

export interface DeviceInfo {
  deviceId: string;
  agentCode: string;
  model: string;
  os: string;
  osVersion: string;
  appVersion: string;
  enrolled: boolean;
  lastSeen: string;
}

export async function checkDevice(
  deviceId: string,
  agentCode: string
): Promise<AdapterResponse<DeviceCheckResult>> {
  return mdmComplianceEngine.post<DeviceCheckResult>("/api/v1/device/check", {
    deviceId,
    agentCode,
  });
}

export async function listDevices(
  agentCode?: string
): Promise<AdapterResponse<DeviceInfo[]>> {
  const params = agentCode ? { agentCode } : undefined;
  return mdmComplianceEngine.get<DeviceInfo[]>("/api/v1/device/list", params);
}

export async function enrollDevice(
  deviceId: string,
  agentCode: string,
  model: string
): Promise<AdapterResponse<DeviceInfo>> {
  return mdmComplianceEngine.post<DeviceInfo>("/api/v1/device/enroll", {
    deviceId,
    agentCode,
    model,
  });
}
