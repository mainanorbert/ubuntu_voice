import { NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

/**
 * Returns the current backend-authenticated profile.
 */
export async function GET(): Promise<NextResponse> {
  const auth_result = await resolve_auth_bearer_for_backend()
  if (!auth_result.ok) return auth_result.response

  let upstream: Response
  try {
    upstream = await fetch(`${get_backend_base_url()}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${auth_result.token}` },
      cache: "no-store",
    })
  } catch {
    return NextResponse.json({ error: "Could not reach the API server." }, { status: 502 })
  }

  const content_type = upstream.headers.get("content-type") ?? ""
  if (content_type.includes("application/json")) {
    return NextResponse.json(await upstream.json(), { status: upstream.status })
  }
  return new NextResponse(await upstream.text(), { status: upstream.status })
}
