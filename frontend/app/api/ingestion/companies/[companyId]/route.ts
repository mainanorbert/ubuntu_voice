import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

type RouteContext = {
  params: Promise<{ companyId: string }>
}

async function proxy_company_request(
  request: NextRequest,
  context: RouteContext,
  method: "PATCH" | "DELETE",
): Promise<NextResponse> {
  const auth_result = await resolve_auth_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const { companyId } = await context.params
  const url = `${get_backend_base_url()}/api/v1/companies/${encodeURIComponent(companyId)}`
  const headers: HeadersInit = { Authorization: `Bearer ${auth_result.token}` }
  let body: string | undefined
  if (method === "PATCH") {
    headers["Content-Type"] = "application/json"
    try {
      body = await request.text()
    } catch {
      return NextResponse.json({ error: "Invalid request body" }, { status: 400 })
    }
  }

  let upstream: Response
  try {
    upstream = await fetch(url, { method, headers, body })
  } catch {
    return NextResponse.json(
      { error: "Ubuntu Voice is temporarily unavailable. Please try again in a moment." },
      { status: 502 },
    )
  }

  if (upstream.status === 204) return new NextResponse(null, { status: 204 })
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

/**
 * Proxies PATCH /api/ingestion/companies/:id to update editable agent metadata.
 */
export async function PATCH(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxy_company_request(request, context, "PATCH")
}

/** Proxies DELETE /api/ingestion/companies/:id to permanently remove an agent. */
export async function DELETE(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxy_company_request(request, context, "DELETE")
}
