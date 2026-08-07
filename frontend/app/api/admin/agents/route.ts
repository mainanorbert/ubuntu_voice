import { NextResponse } from "next/server"
import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

export async function GET(): Promise<NextResponse> {
  const auth = await resolve_auth_bearer_for_backend()
  if (!auth.ok) return auth.response
  try {
    const response = await fetch(`${get_backend_base_url()}/api/v1/companies/admin`, { headers: { Authorization: `Bearer ${auth.token}` }, cache: "no-store" })
    return NextResponse.json(await response.json().catch(() => ({})), { status: response.status })
  } catch {
    return NextResponse.json({ error: "The agent dashboard is temporarily unavailable. Please try again." }, { status: 502 })
  }
}
