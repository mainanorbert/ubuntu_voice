/**
 * Returns the FastAPI base URL without a trailing slash.
 */
export function get_backend_base_url(): string {
  const raw =
    process.env.BACKEND_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "https://ubuntu-voice-b.vercel.app"
  return raw.replace(/\/$/, "")
}
