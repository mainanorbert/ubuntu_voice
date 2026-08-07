import { NextRequest, NextResponse } from "next/server"
import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

export async function PATCH(request: NextRequest, context: { params: Promise<{ agentId: string }> }): Promise<NextResponse> {
  const auth = await resolve_auth_bearer_for_backend()
  if (!auth.ok) return auth.response
  const { agentId } = await context.params
  try {
    const response = await fetch(`${get_backend_base_url()}/api/v1/companies/${encodeURIComponent(agentId)}/approval`, { method: "PATCH", headers: { Authorization: `Bearer ${auth.token}`, "Content-Type": "application/json" }, body: await request.text() })
    return NextResponse.json(await response.json().catch(() => ({})), { status: response.status })
  } catch {
    return NextResponse.json({ error: "The agent status could not be changed. Please try again." }, { status: 502 })
  }
}
