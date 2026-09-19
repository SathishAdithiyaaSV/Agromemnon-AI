'use client'

import { useState } from 'react'

const HOSTS = new Set(['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be'])

/** Returns the video id if the href is a YouTube watch/short link, else null. */
export function youtubeVideoId(href?: string): string | null {
  if (!href) return null
  let url: URL
  try {
    url = new URL(href)
  } catch {
    return null
  }
  if (url.protocol !== 'https:' || !HOSTS.has(url.hostname)) return null

  const id = url.hostname.endsWith('youtu.be')
    ? url.pathname.slice(1)
    : url.pathname === '/watch'
      ? url.searchParams.get('v')
      : url.pathname.startsWith('/embed/') || url.pathname.startsWith('/shorts/')
        ? url.pathname.split('/')[2]
        : null

  return id && /^[\w-]{11}$/.test(id) ? id : null
}

/**
 * A lite YouTube embed: shows the thumbnail and only mounts the iframe once the
 * farmer taps play. Loading every iframe up front would pull ~1MB of YouTube
 * player script per answer, which is slow on the rural connections this app targets.
 */
export function YouTubeEmbed({ videoId, title }: { videoId: string; title: string }) {
  const [playing, setPlaying] = useState(false)

  return (
    <div className="my-3 overflow-hidden rounded-xl border bg-black/5 dark:bg-white/5">
      <div className="relative aspect-video">
        {playing ? (
          <iframe
            className="absolute inset-0 h-full w-full"
            src={`https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0`}
            title={title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        ) : (
          <button
            type="button"
            onClick={() => setPlaying(true)}
            aria-label={`Play video: ${title}`}
            className="group absolute inset-0 h-full w-full cursor-pointer"
          >
            {/* Plain img, not next/image: the thumbnail is a fixed remote URL that
                needs no optimization, and this avoids a remotePatterns config. */}
            <img
              src={`https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`}
              alt=""
              loading="lazy"
              className="absolute inset-0 h-full w-full object-cover"
            />
            <span className="absolute inset-0 flex items-center justify-center bg-black/20 transition-colors group-hover:bg-black/35">
              <span className="flex h-14 w-20 items-center justify-center rounded-xl bg-red-600 text-white shadow-lg">
                <svg viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </span>
            </span>
          </button>
        )}
      </div>
      <a
        href={`https://www.youtube.com/watch?v=${videoId}`}
        target="_blank"
        rel="noopener noreferrer"
        className="block px-3 py-2 text-sm font-medium hover:underline"
      >
        {title}
      </a>
    </div>
  )
}
