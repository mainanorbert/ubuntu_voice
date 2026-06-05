import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server"

const is_protected_route = createRouteMatcher([
  "/chat(.*)",
  "/dashboard(.*)",
  "/usage(.*)",
  "/guardrails(.*)",
  "/evaluations(.*)",
])

export default clerkMiddleware(async (auth, request) => {
  if (is_protected_route(request)) {
    await auth.protect()
  }
})

export const config = {
  matcher: [
    "/((?!.+\\.[\\w]+$|_next).*)",
    "/",
    "/(api|trpc)(.*)",
  ],
}
