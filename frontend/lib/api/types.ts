export type LoginPayload = {
  email: string;
  password: string;
};

export type SignupPayload = {
  email: string;
  password: string;
  organization_name: string;
};

export type UserRole = string;
export type UserType = "internal" | "client";
export type Permission = string;

export type TokenResponse = {
  access_token: string;
  token_type: string;
  role: UserRole;
  user_type: UserType;
  organization_id: string;
  permissions: Permission[];
};

export type MePermissionsResponse = {
  role: UserRole | "";
  permissions: Permission[];
};

export type SignupResponse = {
  message: string;
};

/** Role key must exist as organization_roles.key for the tenant (built-in or custom). */
export type InviteRole = string;

export type CreateInvitePayload = {
  email: string;
  role: InviteRole;
  expires_in_days?: number;
};

export type InviteCreateResponse = {
  message: string;
  token: string;
  invite: {
    id: string;
    email: string;
    organization_id: string;
    role: string;
    status: string;
    expires_at: string;
    created_at: string;
  };
};

export type AcceptInvitePayload = {
  token: string;
  password: string;
};

export type InviteAcceptResponse = {
  message: string;
};

export type InviteListItem = {
  id: string;
  email: string;
  role: string;
  status: "pending" | "accepted";
  created_at: string;
  expires_at: string;
};

export type InviteResendResponse = {
  message: string;
};

/** Must match an organization_roles.key in the current organization. */
export type UserRoleOption = string;

export type OrganizationUser = {
  id: string;
  email: string;
  role: string;
  type: string;
  created_at: string;
};

export type UpdateUserRolePayload = {
  role: UserRoleOption;
};

export type OrganizationRole = {
  id: string;
  organization_id: string;
  name: string;
  key: string;
};

export type PermissionCatalogItem = {
  code: string;
  display_name: string;
};

export type PermissionModuleGroup = {
  module: string;
  permissions: PermissionCatalogItem[];
};

export type ReplaceRolePermissionsPayload = {
  permissions: string[];
};

export type Candidate = {
  id: string;
  organization_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  location: string | null;
  experience_summary: string | null;
  education: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type CandidateCreatePayload = {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  location?: string;
  experience_summary?: string;
  education?: string;
  notes?: string;
};

export type JobStatus = "draft" | "open" | "closed" | "filled";

export type Job = {
  id: string;
  organization_id: string;
  client_id: string;
  title: string;
  description: string | null;
  status: JobStatus;
  created_at: string;
  updated_at: string;
};

export type PipelineStage = "applied" | "screening" | "interview" | "offer" | "placed" | "rejected";
export type PipelineStatus = "active" | "on_hold" | "withdrawn" | "closed";

export type Pipeline = {
  id: string;
  organization_id: string;
  candidate_id: string;
  job_id: string;
  stage: PipelineStage;
  status: PipelineStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
};
