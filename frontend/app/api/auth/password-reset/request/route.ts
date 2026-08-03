import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"

/** Proxies password-reset requests without exposing the backend URL to the browser. */
export async function POST(request: NextRequest): Promise<NextResponse> {
  let upstream: Response
  try {
    upstream = await fetch(`${get_backend_base_url()}/api/v1/auth/password-reset/request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    })
  } catch {
    return NextResponse.json({ error: "We’re unable to send a reset email right now. Please try again in a few minutes." }, { status: 502 })
  }
  const content_type = upstream.headers.get("content-type") ?? ""
  return content_type.includes("application/json")
    ? NextResponse.json(await upstream.json(), { status: upstream.status })
    : new NextResponse(await upstream.text(), { status: upstream.status })
}
