import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_clerk_bearer_for_backend } from "@/lib/server/resolve_clerk_bearer_for_backend"

type RouteContext = {
  params: Promise<{ companyId: string }>
}

/**
 * Proxies GET to return the company plus its uploaded documents for transparency in the UI.
 */
export async function GET(_request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const auth_result = await resolve_clerk_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const { companyId } = await context.params
  const url = `${get_backend_base_url()}/api/v1/companies/${encodeURIComponent(companyId)}/documents`
  let upstream: Response
  try {
    upstream = await fetch(url, {
      headers: { Authorization: `Bearer ${auth_result.token}` },
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

/**
 * Proxies multipart upload to the FastAPI document ingestion endpoint (field name must be `file`).
 */
export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const auth_result = await resolve_clerk_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const { companyId } = await context.params
  let form_data: FormData
  try {
    form_data = await request.formData()
  } catch {
    return NextResponse.json({ error: "Invalid multipart body" }, { status: 400 })
  }

  const url = `${get_backend_base_url()}/api/v1/companies/${encodeURIComponent(companyId)}/documents`
  let upstream: Response
  try {
    upstream = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${auth_result.token}`,
      },
      body: form_data,
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
