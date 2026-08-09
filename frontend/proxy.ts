import { NextRequest, NextResponse } from "next/server"

const AUTH_COOKIE_NAME = "ubuntu_voice_session"
const BACKEND_BASE_URL = (
  process.env.BACKEND_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "https://ubuntu-voice-b.vercel.app"
).replace(/\/$/, "")
const protected_prefixes = [
  "/dashboard",
  "/documents",
  "/usage",
  "/guardrails",
  "/evaluations",
  "/statistics",
]
const admin_only_prefixes = ["/usage", "/guardrails"]

/**
 * Redirects unauthenticated page requests to the manual/Google login page and
 * prevents non-admins from opening administrator-only dashboards.
 */
export async function proxy(request: NextRequest): Promise<NextResponse> {
  const is_protected = protected_prefixes.some(
    (prefix) => request.nextUrl.pathname === prefix || request.nextUrl.pathname.startsWith(`${prefix}/`),
  )
  if (!is_protected) return NextResponse.next()

  const has_session = Boolean(request.cookies.get(AUTH_COOKIE_NAME)?.value)
  if (has_session) {
    const is_admin_only = admin_only_prefixes.some(
      (prefix) => request.nextUrl.pathname === prefix || request.nextUrl.pathname.startsWith(`${prefix}/`),
    )
    if (!is_admin_only) return NextResponse.next()

    const session_token = request.cookies.get(AUTH_COOKIE_NAME)?.value
    try {
      const response = await fetch(`${BACKEND_BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${session_token}` },
        cache: "no-store",
      })
      const profile: unknown = response.ok ? await response.json() : null
      if (typeof profile === "object" && profile !== null && (profile as { is_admin?: unknown }).is_admin === true) {
        return NextResponse.next()
      }
    } catch {
      // Treat unavailable or invalid authorization as insufficient access to this sensitive page.
    }

    return NextResponse.redirect(new URL("/dashboard", request.url))
  }

  const login_url = new URL("/login", request.url)
  login_url.searchParams.set("next", request.nextUrl.pathname)
  return NextResponse.redirect(login_url)
}

export const config = {
  matcher: ["/((?!.+\\.[\\w]+$|_next).*)", "/"],
}
