/**
 * AI-003: Interview question generation API client.
 */
import { apiRequest } from "@/lib/api/client";
import type {
  GenerateQuestionsRequest,
  GenerateQuestionsResponse,
} from "@/lib/api/types";

/**
 * Generate 8-12 role-specific interview questions.
 *
 * @throws ApiError with detail.error === "EMPTY_JOB_DESCRIPTION" | "EMPTY_REQUIRED_SKILLS"
 */
export async function generateInterviewQuestions(
  payload: GenerateQuestionsRequest,
): Promise<GenerateQuestionsResponse> {
  return apiRequest<GenerateQuestionsResponse>("/ai/interview-questions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
