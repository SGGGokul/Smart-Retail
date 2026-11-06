export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  timestamp: string;
  suggestedFollowUps?: string[];
  error?: boolean;
}

export interface AssistantChatRequest {
  message: string;
  conversationId?: string;
}

export interface AssistantChatResponse {
  answer: string;
  conversationId: string;
  suggestedFollowUps?: string[];
}
