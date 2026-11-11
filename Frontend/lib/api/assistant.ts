import { apiRequest } from "./client";
import { ENDPOINTS } from "./endpoints";
import type {
  AssistantChatRequest,
  AssistantChatResponse,
} from "@/types/assistant";

/**
 * Sends user retail queries to the GenAI / LLM assistant service.
 * POST /api/v1/assistant/chat
 */
export async function sendChatMessage(
  payload: AssistantChatRequest,
  signal?: AbortSignal
): Promise<AssistantChatResponse> {
  return apiRequest<AssistantChatResponse>(ENDPOINTS.ASSISTANT_CHAT, {
    method: "POST",
    body: payload as unknown as Record<string, unknown>,
    signal,
  });
}
