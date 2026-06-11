// Typed Forge admin API functions (built on the credentialed `api` client).
import { api } from "./client";

export interface Product {
  id: string; slug: string; name: string; description: string | null;
  features_template: string[]; quotas_template: Record<string, unknown>;
  default_alg: string; is_active: boolean;
}
export interface Customer {
  id: string; name: string; contact_name: string | null; contact_email: string | null; notes: string | null;
}
export interface OperatorUser {
  id: string; email: string; username: string; role: string; is_active: boolean;
  twofa_enabled: boolean; last_login_at: string | null; created_at: string | null;
}
export interface License {
  id: string; license_id: string; customer_id: string; product_id: string;
  mode: "online" | "offline"; term_preset: string; subscription: string;
  active_from: string; active_until: string | null; status: string; binding: string;
  seat_limit: number; seat_used: number; features: string[]; quotas: Record<string, unknown>; issued_at: string;
}
export interface AuditRow {
  id: string; timestamp: string; actor_name: string | null; actor_type: string;
  action: string; resource_type: string | null; resource_id: string | null;
  result: string; reason: string | null; ip: string | null;
}
export interface SigningKey {
  id: string; key_id: string; alg: string; purpose: string; is_active: boolean; created_at: string;
}
interface ListResp<T> { data: T[]; total?: number; }

const pg = (page?: number, size?: number) => (page ? `?page=${page}&page_size=${size ?? 10}` : "");

export const forge = {
  // products
  listProducts: (page?: number, size?: number) => api.get<ListResp<Product>>(`/products${pg(page, size)}`),
  createProduct: (b: Partial<Product>) => api.post<Product>("/products", b),
  updateProduct: (id: string, b: Partial<Product>) => api.patch<Product>(`/products/${id}`, b),
  deleteProduct: (id: string) => api.del(`/products/${id}`),
  // customers
  listCustomers: (page?: number, size?: number) => api.get<ListResp<Customer>>(`/customers${pg(page, size)}`),
  createCustomer: (b: Partial<Customer>) => api.post<Customer>("/customers", b),
  updateCustomer: (id: string, b: Partial<Customer>) => api.patch<Customer>(`/customers/${id}`, b),
  deleteCustomer: (id: string) => api.del(`/customers/${id}`),
  // users (operators)
  listUsers: (page?: number, size?: number) => api.get<ListResp<OperatorUser>>(`/users${pg(page, size)}`),
  createUser: (b: { email: string; username: string; role: string; password?: string }) => api.post<OperatorUser>("/users", b),
  updateUser: (id: string, b: Partial<{ username: string; role: string; is_active: boolean }>) => api.patch<OperatorUser>(`/users/${id}`, b),
  resetUserPassword: (id: string, newPassword?: string) => api.post(`/users/${id}/reset-password`, { new_password: newPassword ?? null }),
  deleteUser: (id: string) => api.del(`/users/${id}`),
  // licenses
  listLicenses: (page?: number, size?: number) => api.get<ListResp<License>>(`/licenses${pg(page, size)}`),
  issueOnline: (b: Record<string, unknown>) =>
    api.post<{ license_id: string; online_code: string; active_until: string | null; seat_limit: number; status: string }>("/licenses:issue-online", b),
  issueOffline: (b: Record<string, unknown>) =>
    api.post<{ license_id: string; offline_blob: string; bound_fingerprint: string; active_until: string | null; status: string }>("/licenses:issue-offline", b),
  revokeLicense: (id: string, reason: string) => api.post(`/licenses/${id}:revoke`, { reason }),
  deleteLicense: (id: string) => api.del(`/licenses/${id}`),
  // audit + keys + crl
  listAudit: (qs = "") => api.get<ListResp<AuditRow>>(`/audit-logs${qs}`),
  listKeys: () => api.get<ListResp<SigningKey>>("/signing-keys"),
  exportPublic: (keyId: string) => api.get<{ data: { public_key: string } }>(`/signing-keys/${keyId}:export-public`),
  generateCrl: () => api.post<{ data: { version: number; entry_count: number } }>("/crl:generate"),
  // anti-clone (design 07): clone alerts + per-license online bindings
  listCloneAlerts: (status = "") =>
    api.get<{ data: CloneAlert[] }>(`/clone-alerts${status ? `?status=${status}` : ""}`),
  resolveCloneAlert: (id: string) => api.post(`/clone-alerts/${id}:resolve`, {}),
  listBindings: (licenseId: string) => api.get<{ data: Binding[] }>(`/licenses/${licenseId}/bindings`),
};

export interface CloneAlert {
  id: string;
  license_id: string;
  detected_at: string | null;
  alive_identities: number;
  seat_limit: number;
  sample: Record<string, unknown> | null;
  status: string;
}

export interface Binding {
  id: string;
  fingerprint: string | null;
  deployment_uid: string | null;
  install_id: string | null;
  cluster_id: string | null;
  status: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_heartbeat_at: string | null;
}
