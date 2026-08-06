"use client"

import { useEffect, useMemo, useState } from "react"
import {
  APIProvider,
  AdvancedMarker,
  InfoWindow,
  Map as GoogleMap,
  useMap,
} from "@vis.gl/react-google-maps"

export type IncidentStatistic = {
  place: string
  type: string
  total_count: number
  updated_at: string
}

export type KnownPlace = {
  name: string
  latitude: number
  longitude: number
}

type IncidentHotspotMapProps = {
  statistics: IncidentStatistic[]
  known_places: KnownPlace[]
}

type HotspotMarker = {
  id: string
  place: string
  type: string
  count: number
  updated_at: string
  position: google.maps.LatLngLiteral
  color: string
  offset: { x: number; y: number }
}

const INCIDENT_TYPES = [
  { name: "Rights Violations", color: "#DC2626" },
  { name: "Casualties", color: "#F97316" },
  { name: "Displacements", color: "#2563EB" },
  { name: "Severe Hunger", color: "#EAB308" },
] as const

const DEFAULT_CENTER = { lat: 5, lng: 25 }

function place_key(value: string): string {
  return value.trim().toLocaleLowerCase()
}

const DOT_SIZE = 18

function cluster_radius(category_count: number): number {
  if (category_count < 2) return 0
  // Arrange equal dots on a ring so neighboring categories touch, clearly
  // communicating that they belong to the same place.
  return DOT_SIZE / (2 * Math.sin(Math.PI / category_count))
}

function create_hotspots(
  statistics: IncidentStatistic[],
  known_places: KnownPlace[]
): HotspotMarker[] {
  const totals = new Map<
    string,
    { place: string; counts: Record<string, number>; updated_at: string }
  >()
  for (const row of statistics) {
    if (
      !INCIDENT_TYPES.some((incident_type) => incident_type.name === row.type)
    )
      continue
    const key = place_key(row.place)
    const entry = totals.get(key) ?? {
      place: row.place.trim(),
      counts: {},
      updated_at: row.updated_at,
    }
    entry.counts[row.type] =
      (entry.counts[row.type] ?? 0) + Math.max(0, Number(row.total_count) || 0)
    if (
      new Date(row.updated_at).getTime() > new Date(entry.updated_at).getTime()
    )
      entry.updated_at = row.updated_at
    totals.set(key, entry)
  }

  const rendered_places = new Set<string>()
  return known_places.flatMap((known_place) => {
    const key = place_key(known_place.name)
    if (rendered_places.has(key)) return []
    rendered_places.add(key)
    const entry = totals.get(key)
    if (!entry) return []

    const reported_types = INCIDENT_TYPES.filter(
      (incident_type) => (entry.counts[incident_type.name] ?? 0) > 0
    )
    return reported_types.map((incident_type, index) => {
      const count = entry.counts[incident_type.name] ?? 0
      const angle = (2 * Math.PI * index) / reported_types.length - Math.PI / 2
      const separation = cluster_radius(reported_types.length)
      return {
        id: `${key}-${incident_type.name}`,
        place: known_place.name,
        type: incident_type.name,
        count,
        updated_at: entry.updated_at,
        position: { lat: known_place.latitude, lng: known_place.longitude },
        color: incident_type.color,
        offset: {
          x: Math.cos(angle) * separation,
          y: Math.sin(angle) * separation,
        },
      }
    })
  })
}

function MapViewport({ hotspots }: { hotspots: HotspotMarker[] }) {
  const map = useMap()

  useEffect(() => {
    if (!map || hotspots.length === 0) return
    const bounds = new google.maps.LatLngBounds()
    hotspots.forEach(({ position }) => bounds.extend(position))
    if (hotspots.length === 1) {
      map.setCenter(hotspots[0].position)
      map.setZoom(9)
      return
    }
    map.fitBounds(bounds, 72)
  }, [hotspots, map])

  return null
}

/** Renders reported incident categories over the Google Maps basemap. */
export function IncidentHotspotMap({
  statistics,
  known_places,
}: IncidentHotspotMapProps) {
  const [selected_hotspot, set_selected_hotspot] =
    useState<HotspotMarker | null>(null)
  const hotspots = useMemo(
    () => create_hotspots(statistics, known_places),
    [known_places, statistics]
  )
  const api_key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY

  if (!api_key) {
    return (
      <div className="flex h-[360px] items-center justify-center px-5 text-center text-sm text-[#607694] sm:h-[460px]">
        The incident map is unavailable right now. Please try again later.
      </div>
    )
  }

  return (
    <APIProvider apiKey={api_key}>
      <GoogleMap
        defaultCenter={DEFAULT_CENTER}
        defaultZoom={3}
        gestureHandling="cooperative"
        disableDefaultUI={false}
        mapId={process.env.NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID ?? "DEMO_MAP_ID"}
        className="h-[360px] w-full sm:h-[460px]"
      >
        <MapViewport hotspots={hotspots} />
        {hotspots.map((hotspot) => {
          return (
            <AdvancedMarker
              key={hotspot.id}
              position={hotspot.position}
              title={`${hotspot.place}: ${hotspot.count} ${hotspot.type}`}
              onClick={() => set_selected_hotspot(hotspot)}
            >
              <div
                style={{
                  transform: `translate(${hotspot.offset.x}px, ${hotspot.offset.y}px)`,
                }}
              >
                <div
                  aria-label={`${hotspot.place}: ${hotspot.count} ${hotspot.type}`}
                  className="cursor-pointer rounded-full border-2 border-white shadow-md transition-transform hover:scale-125 focus-visible:ring-2 focus-visible:ring-[#1E3A8A] focus-visible:ring-offset-2 focus-visible:outline-none"
                  role="button"
                  tabIndex={0}
                  style={{
                    width: DOT_SIZE,
                    height: DOT_SIZE,
                    backgroundColor: hotspot.color,
                  }}
                  onBlur={() => set_selected_hotspot(null)}
                  onFocus={() => set_selected_hotspot(hotspot)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      set_selected_hotspot(hotspot)
                    }
                  }}
                  onMouseEnter={() => set_selected_hotspot(hotspot)}
                  onMouseLeave={() => set_selected_hotspot(null)}
                />
              </div>
            </AdvancedMarker>
          )
        })}
        {selected_hotspot && (
          <InfoWindow
            position={selected_hotspot.position}
            onCloseClick={() => set_selected_hotspot(null)}
          >
            <div className="max-w-52 px-1 py-0.5 text-[#1E3A8A]">
              <p className="font-semibold">{selected_hotspot.place}</p>
              <p className="mt-1 text-sm">{selected_hotspot.type}</p>
              <p className="text-sm">
                Reports: <strong>{selected_hotspot.count}</strong>
              </p>
            </div>
          </InfoWindow>
        )}
      </GoogleMap>
    </APIProvider>
  )
}
