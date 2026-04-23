export type LoginPayload = {
  email: string;
  password: string;
};

export type SignupPayload = {
  email: string;
  password: string;
};

export type UserRole = "admin" | "recruiter" | "client_viewer";

export type TokenResponse = {
  access_token: string;
  token_type: string;
  role: UserRole;
  organization_id: string;
};

export type SignupResponse = {
  message: string;
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
