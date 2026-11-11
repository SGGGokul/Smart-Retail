import type { RequestOptions, ApiErrorEnvelope } from "@/types/api";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://localhost:8000";

export const DEFAULT_TIMEOUT_MS = 10000;

export class ApiClientError extends Error {
  public readonly status: number;
  public readonly isTimeout: boolean;
  public readonly isNetworkError: boolean;
  public readonly details?: unknown;

  constructor(
    message: string,
    options?: {
      status?: number;
      isTimeout?: boolean;
      isNetworkError?: boolean;
      details?: unknown;
    }
  ) {
    super(message);
    this.name = "ApiClientError";
    this.status = options?.status ?? 0;
    this.isTimeout = Boolean(options?.isTimeout);
    this.isNetworkError = Boolean(options?.isNetworkError);
    this.details = options?.details;
  }
}

/**
 * Core HTTP fetch wrapper with timeout, signal cancellation, and standard error decoding.
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, params, headers, body, signal: userSignal, ...rest } = options;

  let url = `${API_BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // If user provided a cancellation signal, pipe its abort event
  if (userSignal) {
    if (userSignal.aborted) {
      clearTimeout(timeoutId);
      throw new ApiClientError("Request was cancelled by user.", { details: userSignal.reason });
    }
    userSignal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  const requestHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...((headers as Record<string, string>) || {}),
  };

  // Prepare payload
  let payloadBody: BodyInit | null = null;
  if (body) {
    if (isFormData || typeof body === "string") {
      payloadBody = body as BodyInit;
    } else {
      payloadBody = JSON.stringify(body);
    }
  }

  try {
    const response = await fetch(url, {
      ...rest,
      headers: requestHeaders,
      body: payloadBody,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }

      let errorMessage = `HTTP error ${response.status}: ${response.statusText}`;

      if (typeof errorBody === "object" && errorBody !== null) {
        const envelope = errorBody as ApiErrorEnvelope;
        if (envelope.error && typeof envelope.error.message === "string") {
          errorMessage = envelope.error.message;
        } else if ("detail" in errorBody && typeof (errorBody as { detail: unknown }).detail === "string") {
          errorMessage = String((errorBody as { detail: string }).detail);
        }
      }

      throw new ApiClientError(errorMessage, {
        status: response.status,
        details: errorBody,
      });
    }

    if (response.status === 204) {
      return {} as T;
    }

    try {
      return (await response.json()) as T;
    } catch (parseErr) {
      throw new ApiClientError(
        `Failed to parse response JSON from ${endpoint}: ${(parseErr as Error).message}`,
        {
          status: response.status,
          details: parseErr,
        }
      );
    }
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof ApiClientError) {
      throw error;
    }

    if (error instanceof Error && error.name === "AbortError") {
      if (userSignal?.aborted) {
        throw new ApiClientError("Request cancelled.", { details: userSignal.reason });
      }
      throw new ApiClientError(`Request timed out after ${timeoutMs}ms: ${endpoint}`, {
        isTimeout: true,
      });
    }

    throw new ApiClientError(
      `Network error connecting to FastAPI backend at ${url}: ${(error as Error).message}`,
      {
        isNetworkError: true,
        details: error,
      }
    );
  }
}
