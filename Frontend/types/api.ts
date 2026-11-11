export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiErrorEnvelope {
  error: ApiErrorDetail;
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  timeoutMs?: number;
  params?: Record<string, string | number | boolean | undefined>;
  body?: BodyInit | Record<string, unknown> | null;
}
