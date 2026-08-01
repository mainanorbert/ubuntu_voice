import { NextResponse } from "next/server"

import { clear_session_cookie } from "@/lib/server/resolve_auth_bearer_for_backend"

/**
 * Clears the local session cookie.
 */
export async function POST(): Promise<NextResponse> {
  const response = NextResponse.json({ ok: true })
  clear_session_cookie(response)
  return response
}
