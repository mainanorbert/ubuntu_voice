import { NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

/** Proxies authenticated statistic requests to the FastAPI monitoring endpoint. */
async function proxy(
  request: Request,
  method: "GET" | "PUT" | "DELETE"
): Promise<NextResponse> {
  const auth_result = await resolve_auth_bearer_for_backend()
  if (!auth_result.ok) {
    return auth_result.response
  }

  const incoming_url = new URL(request.url)
  const path_suffix =
    incoming_url.pathname.split("incident-statistics")[1] ?? ""
  const upstream_url = new URL(
    `${get_backend_base_url()}/api/v1/monitoring/incident-statistics${path_suffix}`
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
      method,
      body: method === "PUT" ? await request.text() : undefined,
      headers: {
        Authorization: `Bearer ${auth_result.token}`,
        ...(method === "PUT" ? { "Content-Type": "application/json" } : {}),
      },
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

export async function GET(request: Request): Promise<NextResponse> {
  return proxy(request, "GET")
}

export async function PUT(request: Request): Promise<NextResponse> {
  return proxy(request, "PUT")
}

export async function DELETE(request: Request): Promise<NextResponse> {
  return proxy(request, "DELETE")
}
