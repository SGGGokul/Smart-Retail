import { NextResponse } from "next/server";
import { isRetailDomainQuery, DOMAIN_REJECTION_MESSAGE } from "@/lib/assistant";

const BACKEND_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://localhost:8000";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => null);
    const message = body?.message ?? body?.query;
    const conversationId = body?.conversationId || `conv-${Date.now()}`;

    if (!message || typeof message !== "string" || !message.trim()) {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "Missing or invalid 'message' in request body.",
          },
        },
        { status: 400 }
      );
    }

    // Domain restriction: reject non-retail queries before forwarding to FastAPI
    if (!isRetailDomainQuery(message)) {
      return NextResponse.json({
        answer: DOMAIN_REJECTION_MESSAGE,
        conversationId,
        suggestedFollowUps: [
          "How many customers visited today?",
          "Which shelves need restocking?",
          "What is the longest checkout queue?",
          "Summarize today's alerts.",
        ],
      });
    }

    // Forward to FastAPI backend service
    const backendRes = await fetch(`${BACKEND_BASE_URL}/api/v1/assistant/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ message: message.trim(), conversationId }),
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      return NextResponse.json(
        {
          error: {
            code: "BACKEND_ERROR",
            message: `FastAPI backend returned ${backendRes.status}: ${errText}`,
          },
        },
        { status: backendRes.status }
      );
    }

    const data = await backendRes.json();
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      {
        error: {
          code: "BACKEND_UNAVAILABLE",
          message: `Unable to reach FastAPI backend service at ${BACKEND_BASE_URL}. (${(err as Error).message})`,
        },
      },
      { status: 503 }
    );
  }
}
