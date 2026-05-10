"use client"

import { UserButton } from "@clerk/nextjs"
import Image from "next/image"
import Link from "next/link"
import { FormEvent, useCallback, useEffect, useRef, useState } from "react"
import {
  ArrowLeft,
  Bot,
  BrainCircuit,
  Building2,
  Globe2,
  Loader2,
  MessageCircle,
  Mic,
  MicOff,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  Volume2,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"
import { cn } from "@/lib/utils"

type ChatRole = "user" | "assistant"

type ChatMessage = {
  id: string
  role: ChatRole
  content: string
  grounded: boolean | null
}

type CompanyResponse = {
  id: string
  name: string
  email: string
  phone: string | null
  owner_id: string
  created_at: string
}

type AgentChatResponse = {
  reply: string
  grounded?: boolean | null
}

type ChatLanguage = "English" | "Swahili" | "French"

type LanguageOption = {
  label: ChatLanguage
  locale: string
}

type SendMessageOptions = {
  show_assistant_reply?: boolean
  show_user_message?: boolean
}

type BrowserSpeechRecognitionAlternative = {
  transcript: string
}

type BrowserSpeechRecognitionResult = {
  isFinal: boolean
  0?: BrowserSpeechRecognitionAlternative
}

type BrowserSpeechRecognitionResultList = {
  length: number
  [index: number]: BrowserSpeechRecognitionResult
}

type BrowserSpeechRecognitionEvent = Event & {
  resultIndex: number
  results: BrowserSpeechRecognitionResultList
}

type BrowserSpeechRecognitionErrorEvent = Event & {
  error: string
}

type BrowserSpeechRecognition = EventTarget & {
  continuous: boolean
  interimResults: boolean
  lang: string
  maxAlternatives: number
  onend: (() => void) | null
  onerror: ((event: BrowserSpeechRecognitionErrorEvent) => void) | null
  onresult: ((event: BrowserSpeechRecognitionEvent) => void) | null
  onstart: (() => void) | null
  abort: () => void
  start: () => void
  stop: () => void
}

type BrowserSpeechRecognitionConstructor = new () => BrowserSpeechRecognition

declare global {
  interface Window {
    SpeechRecognition?: BrowserSpeechRecognitionConstructor
    webkitSpeechRecognition?: BrowserSpeechRecognitionConstructor
  }
}

/**
 * Builds a human-readable error string from common API JSON shapes.
 */
function format_error_payload(data: unknown): string {
  if (typeof data !== "object" || data === null) return "Request failed"
  const err = (data as { error?: unknown }).error
  if (typeof err === "string") return err
  const detail = (data as { detail?: unknown }).detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg)
        }
        return JSON.stringify(item)
      })
      .join("; ")
  }
  return "Request failed"
}

/**
 * Checks whether the browser exposes both speech-to-text and text-to-speech APIs.
 */
function browser_speech_is_supported(): boolean {
  if (typeof window === "undefined") return false
  return Boolean((window.SpeechRecognition ?? window.webkitSpeechRecognition) && window.speechSynthesis)
}

/**
 * Returns the vendor-prefixed or standard SpeechRecognition constructor.
 */
function get_speech_recognition_constructor(): BrowserSpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null
  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

/**
 * Converts browser speech-recognition errors into user-facing guidance.
 */
function format_speech_error(error: string): string {
  if (error === "not-allowed" || error === "service-not-allowed") {
    return "Microphone access is blocked. Allow microphone permission in your browser to use voice mode."
  }
  if (error === "no-speech") {
    return "I did not catch speech yet. Voice mode will keep listening when you are ready."
  }
  if (error === "network") {
    return "Speech recognition could not connect. Try again when your connection is stable."
  }
  return "Voice mode could not hear that clearly. Please try speaking again."
}

/**
 * Returns the visible part of text up to the current speech boundary.
 */
function reveal_text_at_boundary(text: string, char_index: number): string {
  if (char_index < 0) return ""
  const next_space = text.indexOf(" ", char_index)
  const next_break = text.indexOf("\n", char_index)
  const next_stop = [next_space, next_break].filter((index) => index >= 0).sort((a, b) => a - b)[0]
  return text.slice(0, next_stop === undefined ? text.length : next_stop).trimEnd()
}

const language_options: LanguageOption[] = [
  { label: "English", locale: "en-US" },
  { label: "Swahili", locale: "sw-KE" },
  { label: "French", locale: "fr-FR" },
]

const voice_bar_heights = ["h-6", "h-10", "h-7", "h-12", "h-8", "h-14", "h-9", "h-11", "h-7", "h-12", "h-8", "h-10"]

/**
 * Returns the browser speech locale for a supported chat language.
 */
function locale_for_language(language: ChatLanguage): string {
  return language_options.find((option) => option.label === language)?.locale ?? "en-US"
}

/**
 * Renders the active voice-mode surface with animated listening and speaking pulses.
 */
function VoicePulsePanel({
  live_transcript,
  listening,
  pending,
  speaking,
  speech_supported,
  voice_error,
  voice_status,
}: {
  live_transcript: string
  listening: boolean
  pending: boolean
  speaking: boolean
  speech_supported: boolean | null
  voice_error: string | null
  voice_status: string
}) {
  const pulse_active = listening || speaking || live_transcript.length > 0
  const state_label = listening ? "Listening" : pending ? "Thinking" : speaking ? "Speaking" : "Ready"
  const status_text =
    voice_error ?? (speech_supported === false ? "Voice mode is unavailable in this browser." : voice_status)

  return (
    <div className="h-28 shrink-0 overflow-hidden border-t border-border/70 bg-[linear-gradient(135deg,rgba(35,106,85,0.10),rgba(74,157,177,0.10),rgba(213,150,52,0.08))] px-4 py-3 dark:bg-[linear-gradient(135deg,rgba(35,106,85,0.20),rgba(74,157,177,0.14),rgba(213,150,52,0.10))]">
      <div className="flex h-full items-center gap-4">
        <div className="flex shrink-0 items-center justify-center">
          <div className="relative flex size-20 items-center justify-center">
            {pulse_active ? (
              <>
                <span className="ubuntu-voice-ring absolute size-14 rounded-full border border-primary/25" />
                <span className="ubuntu-voice-ring absolute size-16 rounded-full border border-sky-500/20 [animation-delay:350ms]" />
                <span className="ubuntu-voice-ring absolute size-20 rounded-full border border-amber-500/20 [animation-delay:700ms]" />
              </>
            ) : null}
            <div className="relative z-10 flex size-14 items-center justify-center rounded-full border border-white/60 bg-background/90 text-primary shadow-lg shadow-primary/10 backdrop-blur-sm dark:border-white/10">
              {pending ? (
                <Loader2 className="size-5 animate-spin" aria-hidden />
              ) : speaking ? (
                <Volume2 className="size-5" aria-hidden />
              ) : listening ? (
                <Mic className="size-5" aria-hidden />
              ) : (
                <BrainCircuit className="size-5" aria-hidden />
              )}
            </div>
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-background/80 px-2.5 py-1 text-xs font-medium text-foreground shadow-sm ring-1 ring-border/70">
              <Sparkles className="size-3.5 text-primary" aria-hidden />
              Ubuntu Voice AI
            </span>
            <span className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
              {state_label}
            </span>
          </div>

          <div className="mt-3 flex h-10 items-center gap-1.5 overflow-hidden rounded-xl border border-white/60 bg-background/80 px-3 shadow-sm dark:border-white/10">
            {voice_bar_heights.map((height, index) => (
              <span
                key={`${height}-${index}`}
                className={cn(
                  "w-1 shrink-0 rounded-full transition-colors",
                  height,
                  pulse_active
                    ? "ubuntu-voice-wave bg-primary/70 shadow-[0_0_12px_rgba(35,106,85,0.25)]"
                    : "bg-muted-foreground/25",
                )}
                style={{
                  animationDelay: `${index * 70}ms`,
                  animationDuration: `${760 + (index % 4) * 110}ms`,
                }}
              />
            ))}
            <div className="ml-3 min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">
                {live_transcript || status_text}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ChatPage() {
  const [companies, set_companies] = useState<CompanyResponse[]>([])
  const [selected_company_id, set_selected_company_id] = useState<string | null>(null)
  const [messages, set_messages] = useState<ChatMessage[]>([])
  const [draft, set_draft] = useState("")
  const [pending, set_pending] = useState(false)
  const [page_loading, set_page_loading] = useState(true)
  const [error, set_error] = useState<string | null>(null)
  const [speech_supported, set_speech_supported] = useState<boolean | null>(null)
  const [voice_mode_enabled, set_voice_mode_enabled] = useState(false)
  const [listening, set_listening] = useState(false)
  const [speaking, set_speaking] = useState(false)
  const [voice_status, set_voice_status] = useState("Turn on voice mode to speak with Ubuntu Voice.")
  const [voice_error, set_voice_error] = useState<string | null>(null)
  const [live_transcript, set_live_transcript] = useState("")
  const [selected_language, set_selected_language] = useState<ChatLanguage>("English")

  const chat_scroll_ref = useRef<HTMLDivElement | null>(null)
  const list_end_ref = useRef<HTMLDivElement | null>(null)
  const recognition_ref = useRef<BrowserSpeechRecognition | null>(null)
  const listen_retry_timeout_ref = useRef<number | null>(null)
  const final_transcript_ref = useRef("")
  const live_transcript_ref = useRef("")
  const pending_ref = useRef(false)
  const listening_ref = useRef(false)
  const speaking_ref = useRef(false)
  const voice_mode_enabled_ref = useRef(false)
  const selected_company_id_ref = useRef<string | null>(null)
  const selected_language_ref = useRef<ChatLanguage>("English")
  const manual_stop_ref = useRef(false)
  const handle_voice_transcript_ref = useRef<(text: string) => void>(() => {})
  const start_listening_ref = useRef<() => void>(() => {})

  const selected_company = companies.find((c) => c.id === selected_company_id)

  const scroll_to_bottom = useCallback(() => {
    const chat_scroll = chat_scroll_ref.current
    if (chat_scroll) {
      chat_scroll.scrollTop = chat_scroll.scrollHeight
      return
    }
    list_end_ref.current?.scrollIntoView({ behavior: "auto", block: "end" })
  }, [])

  const clear_listen_retry = useCallback(() => {
    if (typeof window === "undefined" || listen_retry_timeout_ref.current === null) return
    window.clearTimeout(listen_retry_timeout_ref.current)
    listen_retry_timeout_ref.current = null
  }, [])

  const queue_listen_restart = useCallback(
    (delay_ms = 450) => {
      if (typeof window === "undefined") return
      clear_listen_retry()
      listen_retry_timeout_ref.current = window.setTimeout(() => {
        listen_retry_timeout_ref.current = null
        start_listening_ref.current()
      }, delay_ms)
    },
    [clear_listen_retry],
  )

  const stop_current_recognition = useCallback((abort = true) => {
    const recognition = recognition_ref.current
    if (!recognition) return
    try {
      if (abort) {
        recognition.abort()
      } else {
        recognition.stop()
      }
    } catch {
      // The browser may throw if recognition has already stopped.
    }
  }, [])

  const append_assistant_message = useCallback((content: string, grounded: boolean | null): string => {
    const message_id = crypto.randomUUID()
    set_messages((prev) => [
      ...prev,
      {
        id: message_id,
        role: "assistant",
        content,
        grounded,
      },
    ])
    return message_id
  }, [])

  const update_assistant_message = useCallback((message_id: string, content: string) => {
    set_messages((prev) =>
      prev.map((message) => (message.id === message_id ? { ...message, content } : message)),
    )
  }, [])

  const speak_response = useCallback((text: string, on_progress?: (visible_text: string) => void): Promise<void> => {
    if (typeof window === "undefined" || !window.speechSynthesis) return Promise.resolve()

    return new Promise((resolve) => {
      window.speechSynthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = locale_for_language(selected_language_ref.current)
      utterance.rate = 0.96
      utterance.pitch = 1.02
      let last_visible_text = ""
      let fallback_interval: number | null = null

      const update_visible_text = (visible_text: string) => {
        if (!on_progress || visible_text === last_visible_text) return
        last_visible_text = visible_text
        on_progress(visible_text)
      }

      const finish = () => {
        if (fallback_interval !== null) {
          window.clearInterval(fallback_interval)
          fallback_interval = null
        }
        update_visible_text(text)
        speaking_ref.current = false
        set_speaking(false)
        resolve()
      }

      utterance.onstart = () => {
        speaking_ref.current = true
        set_speaking(true)
        set_voice_status("Ubuntu Voice is responding. I will listen again when the reply ends.")
        const started_at = window.performance.now()
        fallback_interval = window.setInterval(() => {
          const elapsed_seconds = (window.performance.now() - started_at) / 1000
          const estimated_chars = Math.max(1, Math.floor(elapsed_seconds * 18 * utterance.rate))
          update_visible_text(reveal_text_at_boundary(text, estimated_chars))
        }, 120)
      }
      utterance.onboundary = (event) => {
        if (typeof event.charIndex !== "number") return
        update_visible_text(reveal_text_at_boundary(text, event.charIndex))
      }
      utterance.onend = finish
      utterance.onerror = finish

      window.speechSynthesis.speak(utterance)
    })
  }, [])

  const disable_voice_mode = useCallback(() => {
    clear_listen_retry()
    manual_stop_ref.current = true
    voice_mode_enabled_ref.current = false
    listening_ref.current = false
    speaking_ref.current = false
    set_voice_mode_enabled(false)
    set_listening(false)
    set_speaking(false)
    set_live_transcript("")
    final_transcript_ref.current = ""
    live_transcript_ref.current = ""
    stop_current_recognition(true)
    if (typeof window !== "undefined") window.speechSynthesis?.cancel()
    set_voice_status("Voice mode is off. You can keep using text chat.")
  }, [clear_listen_retry, stop_current_recognition])

  const send_message = useCallback(
    async (message_text?: string, options: SendMessageOptions = {}): Promise<AgentChatResponse | null> => {
      const show_assistant_reply = options.show_assistant_reply ?? true
      const show_user_message = options.show_user_message ?? true
      const text = (message_text ?? draft).trim()
      const company_id = selected_company_id_ref.current
      if (!text || pending_ref.current || !company_id) return null

      set_error(null)
      set_pending(true)
      pending_ref.current = true
      set_draft("")

      if (show_user_message) {
        const user_message: ChatMessage = {
          id: crypto.randomUUID(),
          role: "user",
          content: text,
          grounded: null,
        }
        set_messages((prev) => [...prev, user_message])
      }

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ company_id, message: text, language: selected_language_ref.current }),
        })

        const data: unknown = await res.json().catch(() => ({}))

        if (!res.ok) {
          set_error(format_error_payload(data))
          return null
        }

        const parsed = data as Partial<AgentChatResponse>
        const reply_text = parsed.reply
        if (typeof reply_text !== "string") {
          set_error("Unexpected response from server")
          return null
        }

        const grounded = typeof parsed.grounded === "boolean" ? parsed.grounded : null

        if (show_assistant_reply) append_assistant_message(reply_text, grounded)

        return { reply: reply_text, grounded }
      } catch {
        set_error("Network error while sending your message.")
        return null
      } finally {
        pending_ref.current = false
        set_pending(false)
      }
    },
    [append_assistant_message, draft],
  )

  const handle_voice_transcript = useCallback(
    async (text: string) => {
      const spoken_text = text.trim()
      if (!spoken_text || !voice_mode_enabled_ref.current) return

      clear_listen_retry()
      set_live_transcript("")
      final_transcript_ref.current = ""
      live_transcript_ref.current = ""
      set_voice_error(null)
      set_voice_status("Processing your question from voice...")

      const response = await send_message(spoken_text, { show_assistant_reply: false, show_user_message: true })
      if (!voice_mode_enabled_ref.current) return

      if (!response?.reply) {
        set_voice_status("I could not complete that turn. I am ready to listen again.")
        queue_listen_restart(900)
        return
      }

      const assistant_message_id = append_assistant_message("", response.grounded ?? null)
      await speak_response(response.reply, (visible_text) => update_assistant_message(assistant_message_id, visible_text))

      if (!voice_mode_enabled_ref.current) return
      set_voice_status("Ready for your next question. Speak when the microphone starts.")
      manual_stop_ref.current = false
      queue_listen_restart(500)
    },
    [append_assistant_message, clear_listen_retry, queue_listen_restart, send_message, speak_response, update_assistant_message],
  )

  const start_listening = useCallback(() => {
    clear_listen_retry()
    if (!voice_mode_enabled_ref.current || listening_ref.current || pending_ref.current || speaking_ref.current) return

    const Recognition = get_speech_recognition_constructor()
    if (!Recognition || !browser_speech_is_supported()) {
      set_speech_supported(false)
      set_voice_error("Voice mode needs a Chromium-based browser with SpeechRecognition and SpeechSynthesis.")
      disable_voice_mode()
      return
    }

    if (!selected_company_id_ref.current) {
      set_voice_error("Select a knowledge base before starting voice mode.")
      set_voice_status("Voice mode is waiting for a knowledge base.")
      return
    }

    const recognition = new Recognition()
    recognition_ref.current = recognition
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1
    recognition.lang = locale_for_language(selected_language_ref.current)

    final_transcript_ref.current = ""
    live_transcript_ref.current = ""
    set_live_transcript("")
    set_voice_error(null)
    manual_stop_ref.current = false

    recognition.onstart = () => {
      listening_ref.current = true
      set_listening(true)
      set_voice_status("Listening... pause when you are done and I will respond.")
    }

    recognition.onresult = (event: BrowserSpeechRecognitionEvent) => {
      let interim_text = ""
      let final_text = final_transcript_ref.current

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        const transcript = result?.[0]?.transcript.trim() ?? ""
        if (!transcript) continue
        if (result.isFinal) {
          final_text = `${final_text} ${transcript}`.trim()
        } else {
          interim_text = `${interim_text} ${transcript}`.trim()
        }
      }

      final_transcript_ref.current = final_text
      const combined_text = `${final_text} ${interim_text}`.trim()
      live_transcript_ref.current = combined_text
      set_live_transcript(combined_text)
    }

    recognition.onerror = (event: BrowserSpeechRecognitionErrorEvent) => {
      if (event.error === "aborted") return

      const message = format_speech_error(event.error)
      if (event.error !== "no-speech") set_voice_error(message)
      set_voice_status(message)

      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        voice_mode_enabled_ref.current = false
        set_voice_mode_enabled(false)
        manual_stop_ref.current = true
      }
    }

    recognition.onend = () => {
      if (recognition_ref.current === recognition) recognition_ref.current = null
      listening_ref.current = false
      set_listening(false)

      const spoken_text = (final_transcript_ref.current || live_transcript_ref.current).trim()
      if (!voice_mode_enabled_ref.current || manual_stop_ref.current) return

      if (spoken_text) {
        set_voice_status("Got it. Listening is paused while I prepare the response.")
        handle_voice_transcript_ref.current(spoken_text)
        return
      }

      if (!pending_ref.current && !speaking_ref.current) {
        set_voice_status("I am still here. Start speaking when you are ready.")
        queue_listen_restart(650)
      }
    }

    try {
      recognition.start()
    } catch {
      recognition_ref.current = null
      listening_ref.current = false
      set_listening(false)
      set_voice_error("Voice mode is already active. Please wait a moment and try again.")
    }
  }, [clear_listen_retry, disable_voice_mode, queue_listen_restart])

  const enable_voice_mode = useCallback(() => {
    const supported = browser_speech_is_supported()
    set_speech_supported(supported)

    if (!supported) {
      set_voice_error("Voice mode needs a Chromium-based browser with microphone speech recognition.")
      set_voice_status("Voice mode is unavailable in this browser.")
      return
    }

    if (!selected_company_id_ref.current) {
      set_voice_error("Select a knowledge base before starting voice mode.")
      return
    }

    if (typeof window !== "undefined") window.speechSynthesis.cancel()
    set_voice_error(null)
    set_live_transcript("")
    manual_stop_ref.current = false
    voice_mode_enabled_ref.current = true
    set_voice_mode_enabled(true)
    set_voice_status("Voice mode is on. The microphone will start listening now.")
    queue_listen_restart(200)
  }, [queue_listen_restart])

  const send_typed_message = useCallback(async () => {
    if (voice_mode_enabled_ref.current) {
      clear_listen_retry()
      manual_stop_ref.current = true
      stop_current_recognition(true)
      set_listening(false)
      listening_ref.current = false
    }

    const voice_mode_active = voice_mode_enabled_ref.current
    const response = await send_message(undefined, {
      show_assistant_reply: !voice_mode_active,
      show_user_message: true,
    })
    if (!voice_mode_enabled_ref.current) return

    manual_stop_ref.current = false
    if (response?.reply) {
      const assistant_message_id = append_assistant_message("", response.grounded ?? null)
      await speak_response(response.reply, (visible_text) => update_assistant_message(assistant_message_id, visible_text))
    }
    if (voice_mode_enabled_ref.current) queue_listen_restart(500)
  }, [
    clear_listen_retry,
    append_assistant_message,
    queue_listen_restart,
    send_message,
    speak_response,
    stop_current_recognition,
    update_assistant_message,
  ])

  useEffect(() => {
    scroll_to_bottom()
  }, [messages, scroll_to_bottom])

  useEffect(() => {
    pending_ref.current = pending
  }, [pending])

  useEffect(() => {
    selected_company_id_ref.current = selected_company_id
  }, [selected_company_id])

  useEffect(() => {
    selected_language_ref.current = selected_language
  }, [selected_language])

  useEffect(() => {
    voice_mode_enabled_ref.current = voice_mode_enabled
  }, [voice_mode_enabled])

  useEffect(() => {
    speaking_ref.current = speaking
  }, [speaking])

  useEffect(() => {
    listening_ref.current = listening
  }, [listening])

  useEffect(() => {
    handle_voice_transcript_ref.current = (text: string) => {
      void handle_voice_transcript(text)
    }
  }, [handle_voice_transcript])

  useEffect(() => {
    start_listening_ref.current = start_listening
  }, [start_listening])

  const load_companies = useCallback(async () => {
    const res = await fetch("/api/ingestion/companies")
    const data: unknown = await res.json().catch(() => ({}))
    if (!res.ok) {
      set_error(format_error_payload(data))
      return
    }
    if (!Array.isArray(data)) {
      set_error("Unexpected companies response")
      return
    }
    const list = data as CompanyResponse[]
    set_companies(list)
    set_selected_company_id((prev) => {
      if (list.length === 0) return null
      if (prev && list.some((c) => c.id === prev)) return prev
      return list[0].id
    })
  }, [])

  const bootstrap = useCallback(async () => {
    set_page_loading(true)
    set_error(null)
    try {
      const reg = await fetch("/api/ingestion/register", { method: "POST" })
      const reg_data: unknown = await reg.json().catch(() => ({}))
      if (!reg.ok) {
        set_error(format_error_payload(reg_data))
        return
      }
      await load_companies()
    } finally {
      set_page_loading(false)
    }
  }, [load_companies])

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void bootstrap()
    }, 0)

    return () => window.clearTimeout(timeout)
  }, [bootstrap])

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      set_messages([])
      set_error(null)
      set_live_transcript("")
      final_transcript_ref.current = ""
      live_transcript_ref.current = ""

      if (voice_mode_enabled_ref.current) {
        manual_stop_ref.current = true
        stop_current_recognition(true)
        window.speechSynthesis.cancel()
        set_speaking(false)
        speaking_ref.current = false
        set_voice_status(
          selected_company_id
            ? "Knowledge base changed. Voice mode will listen again in a moment."
            : "Select a knowledge base before using voice mode.",
        )
        if (selected_company_id) {
          manual_stop_ref.current = false
          queue_listen_restart(600)
        }
      }
    }, 0)

    return () => window.clearTimeout(timeout)
  }, [queue_listen_restart, selected_company_id, stop_current_recognition])

  useEffect(() => {
    return () => {
      clear_listen_retry()
      voice_mode_enabled_ref.current = false
      manual_stop_ref.current = true
      stop_current_recognition(true)
      if (typeof window !== "undefined") window.speechSynthesis?.cancel()
    }
  }, [clear_listen_retry, stop_current_recognition])

  const handle_voice_toggle = useCallback(() => {
    if (voice_mode_enabled) {
      disable_voice_mode()
    } else {
      enable_voice_mode()
    }
  }, [disable_voice_mode, enable_voice_mode, voice_mode_enabled])

  const handle_text_submit = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      void send_typed_message()
    },
    [send_typed_message],
  )

  const handle_language_change = useCallback(
    (language: ChatLanguage) => {
      selected_language_ref.current = language
      set_selected_language(language)
      if (!voice_mode_enabled_ref.current) return
      set_voice_status(`Language changed to ${language}. Voice mode will use it from the next turn.`)
      if (listening_ref.current) {
        manual_stop_ref.current = true
        stop_current_recognition(true)
        set_listening(false)
        listening_ref.current = false
        manual_stop_ref.current = false
        queue_listen_restart(300)
      }
    },
    [queue_listen_restart, stop_current_recognition],
  )

  const voice_control_disabled = page_loading || (!selected_company_id && !voice_mode_enabled)
  const voice_button_label = voice_mode_enabled ? "Turn off voice mode" : "Turn on voice mode"
  const voice_state_label = voice_mode_enabled
    ? listening
      ? "Listening"
      : pending
        ? "Processing"
        : speaking
          ? "Speaking"
          : "Ready"
    : "Off"
  const voice_panel_status =
    voice_error ?? (speech_supported === false ? "Voice mode is unavailable in this browser." : voice_status)
  const can_send = !pending && Boolean(draft.trim()) && Boolean(selected_company_id)

  return (
    <div className="relative flex min-h-svh flex-col overflow-hidden bg-background">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[linear-gradient(180deg,rgba(35,106,85,0.14),rgba(213,150,52,0.08),transparent)] dark:bg-[linear-gradient(180deg,rgba(74,157,177,0.14),rgba(35,106,85,0.10),transparent)]"
        aria-hidden
      />

      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/90 px-4 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3">
          <Button variant="ghost" size="icon-sm" asChild>
            <Link href="/" aria-label="Back to home">
              <ArrowLeft />
            </Link>
          </Button>
          <Link href="/" className="flex min-w-0 flex-1 items-center gap-3 transition-opacity hover:opacity-90">
            <Image
              src="/ub_voice.png"
              alt="Ubuntu Voice"
              width={190}
              height={50}
              className="h-9 w-auto max-w-[min(190px,44vw)] object-contain object-left"
              priority
            />
            <span className="hidden rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary sm:inline">
              Community chat
            </span>
          </Link>
          <Button variant="outline" size="sm" className="hidden shrink-0 sm:inline-flex" asChild>
            <Link href="/documents">Create agent</Link>
          </Button>
          <ThemeToggle />
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      <main className="relative z-10 mx-auto grid w-full max-w-6xl flex-1 gap-4 px-4 py-4 lg:grid-cols-[19rem_minmax(0,1fr)] lg:py-6">
        <aside className="flex flex-col gap-4">
          <section className="rounded-2xl border border-border/80 bg-card/90 p-4 shadow-sm backdrop-blur-sm">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
              <Building2 className="size-4 text-primary" aria-hidden />
              Knowledge base
            </div>
            {page_loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Loading knowledge bases...
              </div>
            ) : companies.length === 0 ? (
              <p className="text-sm leading-relaxed text-muted-foreground">
                No knowledge bases yet.{" "}
                <Link href="/documents" className="font-medium text-primary underline-offset-4 hover:underline">
                  Create an agent and upload PDFs
                </Link>{" "}
                before chatting.
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                <label htmlFor="chat-company" className="sr-only">
                  Select knowledge base for RAG
                </label>
                <select
                  id="chat-company"
                  value={selected_company_id ?? ""}
                  onChange={(e) => set_selected_company_id(e.target.value || null)}
                  className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none ring-ring/50 focus-visible:border-ring focus-visible:ring-3"
                >
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.email})
                    </option>
                  ))}
                </select>
                {selected_company && (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Retrieval is scoped to{" "}
                    <span className="font-medium text-foreground">{selected_company.name}</span>
                    &apos;s embedded documents.
                  </p>
                )}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-border/80 bg-card/70 p-4 shadow-sm backdrop-blur-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <ShieldCheck className="size-4 text-primary" aria-hidden />
              Safety scope
            </div>
            <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
              Privacy-first support for displaced people, women, youth, civil society teams, and local peacebuilders.
            </p>
            <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
              <span className="rounded-lg bg-emerald-500/10 px-2.5 py-2 font-medium text-emerald-700 dark:text-emerald-300">
                Grounded
              </span>
              <span className="rounded-lg bg-sky-500/10 px-2.5 py-2 font-medium text-sky-700 dark:text-sky-300">
                Low-bandwidth
              </span>
            </div>
          </section>
        </aside>

        <section className="flex h-[calc(100svh-9rem)] min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border border-border/80 bg-card/95 shadow-xl shadow-black/5 backdrop-blur-sm lg:h-[calc(100svh-7.5rem)]">
          <div className="flex flex-col gap-3 border-b border-border/70 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                  <Globe2 className="size-3.5" aria-hidden />
                  Africa peace support
                </span>
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
                    voice_mode_enabled
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  {voice_mode_enabled ? <Mic className="size-3.5" aria-hidden /> : <MicOff className="size-3.5" aria-hidden />}
                  Voice {voice_state_label}
                </span>
              </div>
              <h1 className="mt-2 truncate text-base font-semibold text-foreground">
                {selected_company ? selected_company.name : "Ubuntu Voice chat"}
              </h1>
            </div>
            <div className="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
              <label htmlFor="chat-language" className="sr-only">
                Response language
              </label>
              <div className="relative">
                <Globe2 className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden />
                <select
                  id="chat-language"
                  value={selected_language}
                  onChange={(event) => handle_language_change(event.target.value as ChatLanguage)}
                  className="h-8 w-full rounded-lg border border-input bg-background pl-8 pr-7 text-sm outline-none ring-ring/50 focus-visible:border-ring focus-visible:ring-3 sm:w-[8.5rem]"
                >
                  {language_options.map((option) => (
                    <option key={option.label} value={option.label}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <Button variant="outline" size="sm" className="w-full shrink-0 sm:w-auto" asChild>
                <Link href="/documents">Manage documents</Link>
              </Button>
            </div>
          </div>

          <div ref={chat_scroll_ref} className="min-h-0 flex-1 space-y-4 overflow-y-auto bg-muted/10 p-4">
            {messages.length === 0 ? (
              <div className="flex min-h-full flex-col items-center justify-center px-3 py-16 text-center">
                <div className="mb-4 flex size-14 items-center justify-center rounded-2xl border border-border bg-background text-primary shadow-sm">
                  <MessageCircle className="size-6" aria-hidden />
                </div>
                <h2 className="text-balance text-lg font-semibold text-foreground">Ask from trusted local knowledge</h2>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
                  {selected_company_id
                    ? "Use text or voice for practical support questions about services, rights, community resources, and peacebuilding guidance."
                    : "Select a knowledge base to start a grounded conversation."}
                </p>
              </div>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className={cn("flex flex-col gap-1.5", m.role === "user" ? "items-end" : "items-start")}
                >
                  <div className={cn("flex max-w-[88%] items-start gap-2", m.role === "user" && "flex-row-reverse")}>
                    <div
                      className={cn(
                        "mt-1 flex size-7 shrink-0 items-center justify-center rounded-full",
                        m.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "border border-border bg-background text-primary",
                      )}
                    >
                      {m.role === "user" ? (
                        <Mic className="size-3.5" aria-hidden />
                      ) : (
                        <Bot className="size-3.5" aria-hidden />
                      )}
                    </div>
                    <div
                      className={cn(
                        "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap shadow-sm",
                        m.role === "user"
                          ? "rounded-tr-md bg-primary text-primary-foreground"
                          : "rounded-tl-md border border-border/80 bg-background text-foreground",
                      )}
                    >
                      {m.content || (
                        <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                          <span className="size-1.5 animate-pulse rounded-full bg-current" />
                          <span className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:120ms]" />
                          <span className="size-1.5 animate-pulse rounded-full bg-current [animation-delay:240ms]" />
                        </span>
                      )}
                    </div>
                  </div>
                  {m.role === "assistant" && m.grounded !== null && (
                    <span
                      className={cn(
                        "ml-9 rounded-full px-2 py-0.5 text-[10px] font-medium",
                        m.grounded
                          ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                          : "bg-amber-500/15 text-amber-800 dark:text-amber-300",
                      )}
                    >
                      {m.grounded ? "From trusted documents" : "No close match in trusted documents"}
                    </span>
                  )}
                </div>
              ))
            )}
            <div ref={list_end_ref} />
          </div>

          {voice_mode_enabled ? (
            <VoicePulsePanel
              live_transcript={live_transcript}
              listening={listening}
              pending={pending}
              speaking={speaking}
              speech_supported={speech_supported}
              voice_error={voice_error}
              voice_status={voice_status}
            />
          ) : null}

          {error ? (
            <div className="border-t border-border bg-destructive/10 px-4 py-2 text-xs text-destructive">
              {error}
            </div>
          ) : null}

          <form className="border-t border-border/70 bg-background/95 p-3" onSubmit={handle_text_submit}>
            <label htmlFor="chat-input" className="sr-only">
              Message
            </label>
            <div className="relative">
              <textarea
                id="chat-input"
                rows={3}
                value={draft}
                disabled={pending || !selected_company_id}
                onChange={(e) => set_draft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault()
                    void send_typed_message()
                  }
                }}
                placeholder={
                  selected_company_id
                    ? voice_mode_enabled
                      ? "Voice mode is active. Type here anytime."
                      : "Ask Ubuntu Voice..."
                    : "Select a knowledge base first..."
                }
                className="h-[5.75rem] w-full resize-none rounded-2xl border border-input bg-background px-4 py-3 pb-12 pl-12 pr-14 text-sm shadow-sm outline-none ring-ring/50 transition-[border-color,box-shadow] placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 disabled:opacity-50"
              />
              <Button
                type="button"
                variant={voice_mode_enabled ? "default" : "outline"}
                size="icon-sm"
                className={cn(
                  "absolute bottom-3 left-3 size-8 rounded-full shadow-sm",
                  voice_mode_enabled && "shadow-primary/20",
                )}
                disabled={voice_control_disabled}
                onClick={handle_voice_toggle}
                aria-label={voice_button_label}
                title={voice_button_label}
              >
                {voice_mode_enabled ? <MicOff className="size-4" aria-hidden /> : <Mic className="size-4" aria-hidden />}
              </Button>
              <Button
                type="submit"
                size="icon-sm"
                className="absolute bottom-3 right-3 size-8 rounded-full"
                disabled={!can_send}
                aria-label="Send message"
                title="Send message"
              >
                {pending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <SendHorizontal className="size-4" aria-hidden />
                )}
              </Button>
            </div>
            {!voice_mode_enabled && (voice_error || speech_supported === false) ? (
              <p className="mt-2 px-1 text-xs leading-relaxed text-destructive">{voice_panel_status}</p>
            ) : null}
          </form>
        </section>
      </main>
    </div>
  )
}
