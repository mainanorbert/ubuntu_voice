import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"

/** Proxies a submitted replacement password to the backend. */
export async function POST(request: NextRequest): Promise<NextResponse> {
  let upstream: Response
  try {
    upstream = await fetch(`${get_backend_base_url()}/api/v1/auth/password-reset/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    })
  } catch {
    return NextResponse.json({ error: "We couldn’t reset your password right now. Please try again in a few minutes." }, { status: 502 })
  }
  const content_type = upstream.headers.get("content-type") ?? ""
  return content_type.includes("application/json")
    ? NextResponse.json(await upstream.json(), { status: upstream.status })
    : new NextResponse(await upstream.text(), { status: upstream.status })
}
