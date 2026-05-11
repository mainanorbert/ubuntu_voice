import { auth } from "@clerk/nextjs/server"
import { NextResponse } from "next/server"

/**
 * Resolves the Clerk session JWT for forwarding to the Python API, or returns an HTTP error.
 */
export async function resolve_clerk_bearer_for_backend(): Promise<
  { ok: true; token: string } | { ok: false; response: NextResponse }
> {
  const { userId, getToken } = await auth()
  if (!userId) {
    return { ok: false, response: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) }
  }
  const session_token = await getToken()
  if (!session_token) {
    return { ok: false, response: NextResponse.json({ error: "Missing Clerk session token" }, { status: 401 }) }
  }
  return { ok: true, token: session_token }
}
