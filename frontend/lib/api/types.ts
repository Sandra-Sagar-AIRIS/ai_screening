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
  /** Present when API exposes candidate provenance (vendor vs internal submission). */
  source_type?: "internal" | "vendor";
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  location: string | null;
  role: string | null;
  stage?: "applied" | "screening" | "shortlisted" | "interview" | "offered" | "hired" | "rejected";
  job_id?: string | null;
  recruiter_id?: string | null;
  resume_s3_key?: string | null;
  resume_file_name?: string | null;
  source?: "manual" | "resume_upload" | "bulk_upload" | "referral" | "agency" | "import" | "merge";
  status?: "active" | "archived" | "deleted";
  years_experience: number | null;
  experience_summary: string | null;
  education: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  parse_status?: "pending" | "processing" | "completed" | "failed" | null;
  parse_error?: string | null;
  parsed_at?: string | null;
  parsed_resume_data?: {
    skills?: string[];
    years_of_experience?: number | null;
    previous_titles?: string[];
    education?: string | null;
    certifications?: string[];
    normalized_keywords?: string[];
  } | null;
};

/** Assigned vendor on a job (GET /jobs/:id/vendors). */
export type JobVendorAssignment = {
  vendor_id: string;
  email: string;
};

/** Row from GET /jobs/:jobId/candidates (single request). */
export type JobCandidateListItem = {
  pipeline_id: string;
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  source_type: "internal" | "vendor";
};

/** Candidate submitted to a job (UI row). */
export type JobCandidateRow = {
  pipeline_id: string;
  candidate: Candidate;
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

export type JobStatus = "draft" | "open" | "paused" | "closed" | "filled";

export type Job = {
  id: string;
  organization_id: string;
  client_id?: string | null;
  title: string;
  description: string | null;
  status: JobStatus;
  paused_reason?: string | null;
  location?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  experience_min_years?: number | null;
  experience_max_years?: number | null;
  employment_type?: string | null;
  urgency?: string | null;
  required_skills?: string[];
  preferred_skills?: string[];
  key_responsibilities?: string[];
  raw_jd_text?: string | null;
  parsing_source?: string | null;
  parsing_status?: string | null;
  created_by?: string | null;
  filled_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type JobMetrics = {
  job_id: string;
  vendor_count: number;
  candidate_count: number;
};

export type JobSubmissionStatus = "pending" | "shortlisted" | "rejected" | "interviewing" | "offered" | "hired";

export type JobSubmission = {
  id: string;
  candidate_id: string;
  job_id: string;
  submission_status: JobSubmissionStatus;
  notes?: string | null;
  created_at: string;
  updated_at: string;
};

export type JobMatchEntry = {
  rank: number;
  candidate_id: string;
  candidate_name?: string | null;
  fit_score: number;
  category_scores: {
    required_skills: number;
    preferred_skills: number;
    experience: number;
    title: number;
    education: number;
  };
  already_submitted: boolean;
  matched_skills: string[];
  missing_skills: string[];
  recommendation: string;
  confidence_score?: number | null;
};

export type JobMatchesResponse = {
  job_id: string;
  matches: JobMatchEntry[];
  total_count: number;
  generated_at: string;
  limit: number;
  offset: number;
};

export type CandidateMatchEntry = {
  job_id: string;
  fit_score: number;
  category_scores: {
    required_skills: number;
    preferred_skills: number;
    experience: number;
    title: number;
    education: number;
  };
  matched_skills: string[];
  missing_skills: string[];
  recommendation: string;
  confidence_score?: number | null;
};

export type CandidateMatchesResponse = {
  candidate_id: string;
  matches: CandidateMatchEntry[];
  total_count: number;
  limit: number;
  offset: number;
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
