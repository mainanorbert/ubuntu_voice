import { auth } from "@clerk/nextjs/server"
import { NextRequest, NextResponse } from "next/server"

const SUPPORTED_LANGUAGES = ["English", "Swahili", "French"] as const
type ChatLanguage = (typeof SUPPORTED_LANGUAGES)[number]

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

function parse_chat_body(body: unknown): { company_id: string; message: string; language: ChatLanguage } | null {
  if (typeof body !== "object" || body === null) return null
  const company_id = (body as { company_id?: unknown }).company_id
  const message = (body as { message?: unknown }).message
  const language = (body as { language?: unknown }).language ?? "English"
  if (typeof company_id !== "string" || company_id.trim().length === 0) return null
  if (typeof message !== "string" || message.trim().length === 0) return null
  if (!is_supported_language(language)) return null
  return { company_id: company_id.trim(), message: message.trim(), language }
}

/**
 * Proxies POST /api/chat to the FastAPI agents chat endpoint so the browser
 * stays same-origin and avoids CORS to the Python API server.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  const { userId, getToken } = await auth()
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
  }
  const session_token = await getToken()
  if (!session_token) {
    return NextResponse.json({ error: "Missing Clerk session token" }, { status: 401 })
  }

  let raw: unknown
  try {
    raw = await request.json()
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }

  const parsed = parse_chat_body(raw)
  if (!parsed) {
    return NextResponse.json(
      { error: "company_id and message are required, and language must be English, Swahili, or French" },
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
        Authorization: `Bearer ${session_token}`,
      },
      body: JSON.stringify({
        company_id: parsed.company_id,
        message: parsed.message,
        language: parsed.language,
      }),
    })
  } catch {
    return NextResponse.json(
      { error: "Could not reach the API server. Is the backend running?" },
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
