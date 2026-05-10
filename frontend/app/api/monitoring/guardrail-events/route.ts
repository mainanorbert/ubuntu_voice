import { NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_clerk_bearer_for_backend } from "@/lib/server/resolve_clerk_bearer_for_backend"

/**
 * Proxies GET /api/monitoring/guardrail-events to the FastAPI monitoring
 * endpoint so the dashboard can render recent guardrail audit rows.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const auth_result = await resolve_clerk_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const incoming_url = new URL(request.url)
  const limit_param = incoming_url.searchParams.get("limit")
  const upstream_url = new URL(`${get_backend_base_url()}/api/v1/monitoring/guardrail-events`)
  if (limit_param) {
    upstream_url.searchParams.set("limit", limit_param)
  }

  let upstream: Response
  try {
    upstream = await fetch(upstream_url.toString(), {
      headers: { Authorization: `Bearer ${auth_result.token}` },
      cache: "no-store",
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
