import { NextRequest, NextResponse } from "next/server"
import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

export async function GET(request: NextRequest): Promise<NextResponse> {
  const auth = await resolve_auth_bearer_for_backend()
  if (!auth.ok) return auth.response
  try {
    const query = new URLSearchParams()
    for (const key of ["page", "page_size", "search"]) {
      const value = request.nextUrl.searchParams.get(key)
      if (value !== null) query.set(key, value)
    }
    const suffix = query.size ? `?${query.toString()}` : ""
    const response = await fetch(
      `${get_backend_base_url()}/api/v1/companies/admin${suffix}`,
      { headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store" }
    )
    return NextResponse.json(await response.json().catch(() => ({})), {
      status: response.status,
    })
  } catch {
    return NextResponse.json(
      {
        error:
          "The agent dashboard is temporarily unavailable. Please try again.",
      },
      { status: 502 }
    )
  }
}
