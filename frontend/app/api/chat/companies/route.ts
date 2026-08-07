import { NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"

/** Returns the available agents for guest and signed-in web chat. */
export async function GET(): Promise<NextResponse> {
  try {
    const upstream = await fetch(`${get_backend_base_url()}/api/v1/companies/public`)
    const data: unknown = await upstream.json().catch(() => ({}))
    return NextResponse.json(data, { status: upstream.status })
  } catch {
    return NextResponse.json(
      { error: "Ubuntu Voice is temporarily unavailable. Please try again in a moment." },
      { status: 502 },
    )
  }
}
