import { NextResponse } from "next/server"
import { get_backend_base_url } from "@/lib/backend_base_url"
import { resolve_auth_bearer_for_backend } from "@/lib/server/resolve_auth_bearer_for_backend"

async function proxy(request: Request, method: string) {
  const auth = await resolve_auth_bearer_for_backend()
  if (!auth.ok) return auth.response
  let body: string | undefined
  if (method !== "GET" && method !== "DELETE") body = await request.text()
  try {
    const upstream = await fetch(`${get_backend_base_url()}/api/v1/monitoring/known-places${new URL(request.url).pathname.split("known-places")[1] ?? ""}`, {
      method, body, headers: { Authorization: `Bearer ${auth.token}`, ...(body ? { "Content-Type": "application/json" } : {}) }, cache: "no-store",
    })
    if (upstream.status === 204) return new NextResponse(null, { status: 204 })
    return NextResponse.json(await upstream.json(), {
      status: upstream.status,
      headers: { "Cache-Control": "no-store, max-age=0" },
    })
  } catch { return NextResponse.json({ error: "The places service is temporarily unavailable. Please try again." }, { status: 502 }) }
}
export async function GET(request: Request) { return proxy(request, "GET") }
export async function POST(request: Request) { return proxy(request, "POST") }
export async function PUT(request: Request) { return proxy(request, "PUT") }
export async function DELETE(request: Request) { return proxy(request, "DELETE") }
