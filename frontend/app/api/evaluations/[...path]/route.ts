import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_clerk_bearer_for_backend } from "@/lib/server/resolve_clerk_bearer_for_backend"

async function proxy_evaluation_request(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const auth_result = await resolve_clerk_bearer_for_backend()
  if (!auth_result.ok) return auth_result.response

  const { path } = await context.params
  const upstream_url = `${get_backend_base_url()}/api/v1/evaluations/${path.map(encodeURIComponent).join("/")}`
  const body = request.method === "GET" || request.method === "DELETE" ? undefined : await request.text()
  let upstream: Response
  try {
    upstream = await fetch(upstream_url, {
      method: request.method,
      headers: {
        Authorization: `Bearer ${auth_result.token}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body,
      cache: "no-store",
    })
  } catch {
    return NextResponse.json({ error: "Could not reach the API server." }, { status: 502 })
  }

  if (upstream.status === 204) return new NextResponse(null, { status: 204 })
  const content_type = upstream.headers.get("content-type") ?? ""
  if (content_type.includes("application/json")) {
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  }
  return new NextResponse(await upstream.text(), { status: upstream.status })
}

export const GET = proxy_evaluation_request
export const POST = proxy_evaluation_request
export const DELETE = proxy_evaluation_request
