"use client"

import { useEffect, useState } from "react"
import { Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"

import { Button } from "@/components/ui/button"

/**
 * Switches between light and dark color schemes using the active resolved theme.
 */
export function ThemeToggle() {
  const [mounted, set_mounted] = useState(false)
  const { resolvedTheme, setTheme } = useTheme()

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      set_mounted(true)
    })
    return () => cancelAnimationFrame(id)
  }, [])

  function toggle_theme() {
    setTheme(resolvedTheme === "dark" ? "light" : "dark")
  }

  if (!mounted) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        className="shrink-0 text-muted-foreground"
        disabled
        aria-hidden
      >
        <Sun className="size-4 opacity-50" aria-hidden />
      </Button>
    )
  }

  const is_dark = resolvedTheme === "dark"

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      className="shrink-0 text-muted-foreground hover:text-foreground"
      onClick={toggle_theme}
      aria-label={is_dark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {is_dark ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
    </Button>
  )
}
