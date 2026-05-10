import { NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_clerk_bearer_for_backend } from "@/lib/server/resolve_clerk_bearer_for_backend"

/**
 * Proxies POST /api/ingestion/register to the FastAPI user registration sync endpoint.
 */
export async function POST(): Promise<NextResponse> {
  const auth_result = await resolve_clerk_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const url = `${get_backend_base_url()}/api/v1/users/register`
  let upstream: Response
  try {
    upstream = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${auth_result.token}`,
      },
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
