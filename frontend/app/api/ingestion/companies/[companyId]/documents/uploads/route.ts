import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_clerk_bearer_for_backend } from "@/lib/server/resolve_clerk_bearer_for_backend"

type RouteContext = {
  params: Promise<{ companyId: string }>
}

/**
 * Proxies the signed-upload mint request to the FastAPI backend.
 *
 * The backend either returns a list of pre-signed Supabase URLs (mode="direct")
 * or signals mode="multipart" so the client can fall back to the legacy upload.
 */
export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const auth_result = await resolve_clerk_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const { companyId } = await context.params

  let body_text: string
  try {
    body_text = await request.text()
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 })
  }

  const url = `${get_backend_base_url()}/api/v1/companies/${encodeURIComponent(companyId)}/documents/uploads`
  let upstream: Response
  try {
    upstream = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${auth_result.token}`,
        "Content-Type": "application/json",
      },
      body: body_text,
    })
  } catch {
    return NextResponse.json(
      { error: "Could not reach the API server. Is the backend running?" },
      { status: 502 },
    )
  }

  const content_type = upstream.headers.get("content-type") ?? ""
  if (content_type.includes("application/json")) {
    const data: unknown = await upstream.json()
    return NextResponse.json(data, { status: upstream.status })
  }

  const text = await upstream.text()
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  })
}
