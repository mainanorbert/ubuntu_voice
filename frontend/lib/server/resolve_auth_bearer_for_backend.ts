import { cookies } from "next/headers"
import { NextResponse } from "next/server"

export const AUTH_COOKIE_NAME = "ubuntu_voice_session"

/**
 * Resolves the first-party backend session token from the HttpOnly cookie.
 */
export async function get_session_token(): Promise<string | null> {
  const cookie_store = await cookies()
  return cookie_store.get(AUTH_COOKIE_NAME)?.value ?? null
}

/**
 * Returns a bearer token for backend proxy routes, or a 401 response.
 */
export async function resolve_auth_bearer_for_backend(): Promise<
  { ok: true; token: string } | { ok: false; response: NextResponse }
> {
  const session_token = await get_session_token()
  if (!session_token) {
    return { ok: false, response: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) }
  }
  return { ok: true, token: session_token }
}

/**
 * Adds the first-party session cookie to a route response.
 */
export function set_session_cookie(response: NextResponse, token: string, max_age_seconds: number): void {
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: token,
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: max_age_seconds,
  })
}

/**
 * Clears the first-party session cookie from a route response.
 */
export function clear_session_cookie(response: NextResponse): void {
  response.cookies.set({
    name: AUTH_COOKIE_NAME,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 0,
  })
}
