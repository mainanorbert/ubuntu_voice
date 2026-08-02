import { NextRequest, NextResponse } from "next/server"

import { get_backend_base_url } from "@/lib/backend_base_url"
import { set_session_cookie } from "@/lib/server/resolve_auth_bearer_for_backend"

const GOOGLE_STATE_COOKIE = "ubuntu_voice_google_oauth_state"

type AuthPayload = {
  token?: unknown
  expires_in?: unknown
}

/**
 * Completes Google OAuth by letting the backend exchange the code for a local session.
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const code = request.nextUrl.searchParams.get("code")
  const state = request.nextUrl.searchParams.get("state")
  const expected_state = request.cookies.get(GOOGLE_STATE_COOKIE)?.value
  if (!code || !state || !expected_state || state !== expected_state) {
    return NextResponse.redirect(new URL("/login?error=google_state", request.url))
  }

  const redirect_uri = new URL("/api/auth/google/callback", request.nextUrl.origin).toString()
  let upstream: Response
  try {
    upstream = await fetch(`${get_backend_base_url()}/api/v1/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, redirect_uri }),
      cache: "no-store",
    })
  } catch {
    return NextResponse.redirect(new URL("/login?error=api_unavailable", request.url))
  }

  if (!upstream.ok) {
    return NextResponse.redirect(new URL("/login?error=google_failed", request.url))
  }

  const data = (await upstream.json()) as AuthPayload
  if (typeof data.token !== "string" || typeof data.expires_in !== "number") {
    return NextResponse.redirect(new URL("/login?error=google_failed", request.url))
  }

  const response = NextResponse.redirect(new URL("/documents", request.url))
  set_session_cookie(response, data.token, data.expires_in)
  response.cookies.set({
    name: GOOGLE_STATE_COOKIE,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  })
  return response
}
