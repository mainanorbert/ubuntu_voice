import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { set_session_cookie } from "@/lib/server/resolve_auth_bearer_for_backend"

type AuthPayload = {
  token?: unknown
  expires_in?: unknown
}

/**
 * Proxies manual login to the backend and stores the returned session in an HttpOnly cookie.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  return proxy_manual_auth(request, "/api/v1/auth/login")
}

async function proxy_manual_auth(request: NextRequest, path: string): Promise<NextResponse> {
  let body_text: string
  try {
    body_text = await request.text()
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
  }

  let upstream: Response
  try {
    upstream = await fetch(`${get_backend_base_url()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body_text,
      cache: "no-store",
    })
  } catch {
    return NextResponse.json({ error: "Ubuntu Voice is temporarily unavailable. Please try again in a moment." }, { status: 502 })
  }

  const content_type = upstream.headers.get("content-type") ?? ""
  if (!content_type.includes("application/json")) {
    return new NextResponse(await upstream.text(), { status: upstream.status })
  }

  const data = (await upstream.json()) as AuthPayload
  const response = NextResponse.json(data, { status: upstream.status })
  if (upstream.ok && typeof data.token === "string" && typeof data.expires_in === "number") {
    set_session_cookie(response, data.token, data.expires_in)
  }
  return response
}
