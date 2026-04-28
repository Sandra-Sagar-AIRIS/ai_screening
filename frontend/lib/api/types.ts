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

export type InviteRole = "recruiter" | "client_viewer";

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

export type UserRoleOption = "admin" | "recruiter" | "client_viewer";

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

export type RoleKey = "admin" | "recruiter" | "client_viewer";

export type RolePermissionsResponse = Record<RoleKey, string[]>;

export type UpdateRolePermissionsPayload = {
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
