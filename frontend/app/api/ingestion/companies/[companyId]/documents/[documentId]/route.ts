import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

type RouteContext = {
  params: Promise<{ companyId: string; documentId: string }>
}

/** Proxies permanent document deletion to the authenticated backend endpoint. */
export async function DELETE(
  _request: NextRequest,
  context: RouteContext
): Promise<NextResponse> {
  const auth_result = await resolve_auth_bearer_for_backend()
  if (!auth_result.ok) return auth_result.response

  const { companyId, documentId } = await context.params
  const url = `${get_backend_base_url()}/api/v1/companies/${encodeURIComponent(companyId)}/documents/${encodeURIComponent(documentId)}`

  let upstream: Response
  try {
    upstream = await fetch(url, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${auth_result.token}` },
    })
  } catch {
    return NextResponse.json(
      { error: "Ubuntu Voice is temporarily unavailable. Please try again in a moment." },
      { status: 502 }
    )
  }

  if (upstream.status === 204) return new NextResponse(null, { status: 204 })

  const content_type = upstream.headers.get("content-type") ?? ""
  if (content_type.includes("application/json")) {
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  }
  return new NextResponse(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  })
}
