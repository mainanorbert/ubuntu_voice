import { NextRequest, NextResponse } from "next/server"

const GOOGLE_STATE_COOKIE = "ubuntu_voice_google_oauth_state"

/**
 * Starts a minimal Google OAuth web-server flow.
 */
export async function GET(request: NextRequest): Promise<NextResponse> {
  const google_client_id = process.env.GOOGLE_CLIENT_ID
  if (!google_client_id) {
    return NextResponse.redirect(new URL("/login?error=google_not_configured", request.url))
  }

  const redirect_uri = new URL("/api/auth/google/callback", request.nextUrl.origin).toString()
  const state = crypto.randomUUID()
  const authorize_url = new URL("https://accounts.google.com/o/oauth2/v2/auth")
  authorize_url.searchParams.set("client_id", google_client_id)
  authorize_url.searchParams.set("redirect_uri", redirect_uri)
  authorize_url.searchParams.set("response_type", "code")
  authorize_url.searchParams.set("scope", "openid email profile")
  authorize_url.searchParams.set("state", state)
  authorize_url.searchParams.set("prompt", "select_account")

  const response = NextResponse.redirect(authorize_url)
  response.cookies.set({
    name: GOOGLE_STATE_COOKIE,
    value: state,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 10 * 60,
  })
  return response
}
