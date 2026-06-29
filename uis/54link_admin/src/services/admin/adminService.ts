import apiClient from '../api';
import { BACKEND_URL } from '../../const';

const API_BASE = `${BACKEND_URL}/admin/admin`;
const ORCHESTRATOR_ADMIN_API = `${BACKEND_URL}/orchestrator/admin`;

export async function createAdmin(payload: {
  email: string;
  firstName: string;
  lastName: string;
  phone: string;
  uin: string;
  password: string;
}) {
  const { data } = await apiClient.post(ORCHESTRATOR_ADMIN_API, payload);
  return data;
}

export async function getAdminById(id: string | number) {
  const { data } = await apiClient.get(`${API_BASE}/${id}`);
  return data;
}

export async function getAdminByKeycloakId(keycloakId: string) {
  const { data } = await apiClient.get(`${API_BASE}/keycloak/${keycloakId}`);
  return data;
}

export async function getAdmins() {
  const { data } = await apiClient.get(API_BASE);
  return data;
}

export async function suspendAdmin(id: string | number) {
  const { data } = await apiClient.patch(`${API_BASE}/${id}/suspend`);
  return data;
}

export async function unsuspendAdmin(id: string | number) {
  const { data } = await apiClient.patch(`${API_BASE}/${id}/unsuspend`);
  return data;
}
