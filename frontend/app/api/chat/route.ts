import { NextRequest, NextResponse } from "next/server"

import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

const SUPPORTED_LANGUAGES = ["English", "Swahili", "French", "Arabic", "Portuguese"] as const
type ChatLanguage = (typeof SUPPORTED_LANGUAGES)[number]
type ChatHistoryMessage = { role: "user" | "assistant"; content: string }
type ReportLocation = { latitude: number; longitude: number; accuracy_m: number }

function get_backend_base_url(): string {
  const raw =
    process.env.BACKEND_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "https://css-1-rcyk.onrender.com"
  return raw.replace(/\/$/, "")
}

function is_supported_language(value: unknown): value is ChatLanguage {
  return typeof value === "string" && SUPPORTED_LANGUAGES.includes(value as ChatLanguage)
}

function parse_history(value: unknown): ChatHistoryMessage[] | null {
  if (value === undefined) return []
  if (!Array.isArray(value) || value.length > 8) return null
  const history: ChatHistoryMessage[] = []
  for (const item of value) {
    if (typeof item !== "object" || item === null) return null
    const role = (item as { role?: unknown }).role
    const content = (item as { content?: unknown }).content
    if ((role !== "user" && role !== "assistant") || typeof content !== "string") return null
    const trimmed = content.trim()
    if (!trimmed || trimmed.length > 1200) return null
    history.push({ role, content: trimmed })
  }
  return history
}

function parse_location(value: unknown): ReportLocation | null | undefined {
  if (value === undefined) return undefined
  if (typeof value !== "object" || value === null) return null
  const { latitude, longitude, accuracy_m } = value as Record<string, unknown>
  if (
    typeof latitude !== "number" || !Number.isFinite(latitude) || latitude < -90 || latitude > 90 ||
    typeof longitude !== "number" || !Number.isFinite(longitude) || longitude < -180 || longitude > 180 ||
    typeof accuracy_m !== "number" || !Number.isFinite(accuracy_m) || accuracy_m < 0 || accuracy_m > 100000
  ) return null
  return { latitude, longitude, accuracy_m }
}

function parse_chat_body(
  body: unknown,
): { company_id: string; message: string; language: ChatLanguage; history: ChatHistoryMessage[]; location?: ReportLocation } | null {
  if (typeof body !== "object" || body === null) return null
  const company_id = (body as { company_id?: unknown }).company_id
  const message = (body as { message?: unknown }).message
  const language = (body as { language?: unknown }).language ?? "English"
  const history = parse_history((body as { history?: unknown }).history)
  const location = parse_location((body as { location?: unknown }).location)
  if (typeof company_id !== "string" || company_id.trim().length === 0) return null
  if (typeof message !== "string" || message.trim().length === 0) return null
  if (!is_supported_language(language)) return null
  if (history === null || location === null) return null
  return { company_id: company_id.trim(), message: message.trim(), language, history, ...(location ? { location } : {}) }
}

/**
 * Proxies POST /api/chat to the FastAPI agents chat endpoint so the browser
 * stays same-origin and avoids CORS to the Python API server.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const auth_result = await resolve_auth_bearer_for_backend()

  let raw: unknown
  try {
    raw = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }

  const parsed = parse_chat_body(raw)
  if (!parsed) {
    return NextResponse.json(
      {
        error:
          "company_id and message are required, language must be English, Swahili, French, Arabic, or Portuguese, and history must be recent chat turns",
      },
      { status: 400 },
    )
  }

  const url = `${get_backend_base_url()}/api/v1/agents/chat`
  let upstream: Response
  try {
    upstream = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(auth_result.ok ? { Authorization: `Bearer ${auth_result.token}` } : {}),
      },
      body: JSON.stringify({
        company_id: parsed.company_id,
        message: parsed.message,
        language: parsed.language,
        history: parsed.history,
        ...(parsed.location ? { location: parsed.location } : {}),
      }),
    })
  } catch {
    return NextResponse.json(
      { error: "We’re having trouble connecting right now. Please try again in a moment." },
      { status: 502 },
    )
  }

  const contentType = upstream.headers.get("content-type") ?? ""
  if (contentType.includes("application/json")) {
    const data: unknown = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  }

  const text = await upstream.text()
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  })
}
