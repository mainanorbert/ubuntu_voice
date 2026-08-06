import { NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

/**
 * Proxies GET /api/monitoring/incident-statistics to the FastAPI monitoring endpoint.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const auth_result = await resolve_auth_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const incoming_url = new URL(request.url)
  const upstream_url = new URL(
    `${get_backend_base_url()}/api/v1/monitoring/incident-statistics`
  )
  for (const parameter of ["agent_id", "page", "page_size"]) {
    const value = incoming_url.searchParams.get(parameter)
    if (value) {
      upstream_url.searchParams.set(parameter, value)
    }
  }

  let upstream: Response
  try {
    upstream = await fetch(upstream_url.toString(), {
      headers: { Authorization: `Bearer ${auth_result.token}` },
      cache: "no-store",
    })
  } catch {
    return NextResponse.json(
      {
        error: "The statistics service is unavailable. Please try again later.",
      },
      { status: 502 }
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
