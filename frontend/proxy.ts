import { NextRequest, NextResponse } from "next/server"

const AUTH_COOKIE_NAME = "ubuntu_voice_session"
const protected_prefixes = [
  "/dashboard",
  "/documents",
  "/usage",
  "/guardrails",
  "/evaluations",
  "/statistics",
]

/**
 * Redirects unauthenticated page requests to the manual/Google login page.
 */
export function proxy(request: NextRequest): NextResponse {
  const is_protected = protected_prefixes.some(
    (prefix) => request.nextUrl.pathname === prefix || request.nextUrl.pathname.startsWith(`${prefix}/`),
  )
  if (!is_protected) return NextResponse.next()

  const has_session = Boolean(request.cookies.get(AUTH_COOKIE_NAME)?.value)
  if (has_session) return NextResponse.next()

  const login_url = new URL("/login", request.url)
  login_url.searchParams.set("next", request.nextUrl.pathname)
  return NextResponse.redirect(login_url)
}

export const config = {
  matcher: ["/((?!.+\\.[\\w]+$|_next).*)", "/"],
}
