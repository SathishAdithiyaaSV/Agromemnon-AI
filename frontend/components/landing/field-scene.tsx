/**
 * The animated band that closes the hero: a looping farm scene — clouds crossing
 * a hazy sun, birds, a tractor working a ridge, and a foreground of stalks bending
 * in the wind.
 *
 * Drawn as one inline SVG rather than shipped as a video. A hero video on this
 * product would be the single heaviest thing on the page, and the farmers it is
 * for are on metered 4G; this is a few kilobytes of markup, animates entirely on
 * transform/opacity, and inherits the theme so it works in dark mode for free.
 * `.field-scene` is the hook the reduced-motion rule in globals.css switches off.
 */

/*
  Sky positions are kept in the lower two thirds of the viewBox on purpose. The
  SVG is bottom-anchored with `slice`, so on a viewport wider than the 6:1 art
  it is the *top* of the viewBox that gets cropped — anything parked above y≈48
  disappears on a wide monitor.
*/
const CLOUDS = [
  { y: 56, scale: 1, opacity: 0.5, duration: 78, delay: 0, rain: false },
  { y: 76, scale: 0.68, opacity: 0.38, duration: 104, delay: -34, rain: true },
  { y: 50, scale: 0.82, opacity: 0.3, duration: 126, delay: -70, rain: false },
]

/* The shower that one cloud carries. Offsets are in the cloud's own coordinates,
   so the rain travels with it. */
const RAIN = [
  { x: 36, delay: 0 },
  { x: 52, delay: -0.55 },
  { x: 68, delay: -1.1 },
  { x: 84, delay: -0.3 },
  { x: 100, delay: -0.85 },
]

const BIRDS = [
  { y: 96, scale: 1, duration: 34, delay: -4, flap: 0.42 },
  { y: 110, scale: 0.75, duration: 41, delay: -16, flap: 0.5 },
  { y: 86, scale: 0.6, duration: 47, delay: -27, flap: 0.36 },
]

/* Seed husks lifting off the crop. Short list, long durations — the effect is
   meant to be noticed on the second look, not the first. */
const MOTES = Array.from({ length: 12 }, (_, i) => ({
  left: 4 + i * 8 + ((i * 29) % 6),
  duration: 9 + ((i * 11) % 7),
  delay: -((i * 17) % 13),
  drift: ((i % 5) - 2) * 26,
  size: i % 3 === 0 ? 3 : 2,
}))

/* Foreground stalks: deterministic pseudo-spread, so the server and the client
   render the same field and React does not complain about a hydration mismatch. */
const STALKS = Array.from({ length: 34 }, (_, i) => ({
  x: 12 + i * 42 + ((i * 37) % 19),
  height: 34 + ((i * 53) % 26),
  duration: 3.6 + ((i * 7) % 11) * 0.22,
  delay: -((i * 13) % 40) * 0.12,
  ear: i % 3 === 0,
}))

export function FieldScene() {
  return (
    <div
      className="field-scene pointer-events-none relative h-44 w-full overflow-hidden sm:h-56 lg:h-72 xl:h-80"
      aria-hidden
    >
      {/* Sun: a soft disc that breathes, sitting behind the hills. */}
      <div
        className="absolute right-[12%] top-4 size-28 rounded-full bg-accent/30 blur-2xl"
        style={{ animation: 'sun-glow 7s ease-in-out infinite' }}
      />
      <div className="absolute right-[15%] top-10 size-12 rounded-full bg-accent/45 blur-md" />

      <svg
        viewBox="0 0 1440 240"
        preserveAspectRatio="xMidYMax slice"
        className="absolute inset-0 size-full"
      >
        {/* ------------------------------------------------------------- sky */}
        {CLOUDS.map((cloud) => (
          <g
            key={`${cloud.y}-${cloud.duration}`}
            style={{
              ['--from' as string]: '-22%',
              ['--to' as string]: '124%',
              animation: `cross ${cloud.duration}s linear ${cloud.delay}s infinite`,
            }}
          >
            <g transform={`translate(0 ${cloud.y}) scale(${cloud.scale})`} opacity={cloud.opacity}>
              <path
                d="M40 34c-13 0-23-8-23-18S27-2 40-2c6 0 12 2 16 6 5-8 14-13 24-13 15 0 27 11 28 25 10 1 18 9 18 18s-9 18-20 18H40Z"
                className="fill-primary/40"
              />
              {cloud.rain
                ? RAIN.map((drop) => (
                    <line
                      key={drop.x}
                      x1={drop.x}
                      y1="38"
                      x2={drop.x - 2}
                      y2="46"
                      strokeWidth="2"
                      strokeLinecap="round"
                      className="stroke-water/70"
                      style={{ animation: `rainfall 1.5s linear ${drop.delay}s infinite` }}
                    />
                  ))
                : null}
            </g>
          </g>
        ))}

        {BIRDS.map((bird) => (
          <g
            key={`${bird.y}-${bird.duration}`}
            style={{
              ['--from' as string]: '-8%',
              ['--to' as string]: '112%',
              animation: `cross ${bird.duration}s linear ${bird.delay}s infinite`,
            }}
          >
            <g transform={`translate(0 ${bird.y}) scale(${bird.scale})`}>
              <path
                d="M0 6C4 6 7 3 9 0c2 3 5 6 9 6"
                fill="none"
                strokeWidth="1.8"
                strokeLinecap="round"
                className="origin-self stroke-foreground/35"
                style={{ animation: `flap ${bird.flap}s ease-in-out infinite` }}
              />
            </g>
          </g>
        ))}

        {/* ----------------------------------------------------------- hills */}
        <path
          d="M0 132c150-34 268 12 402 6 134-6 214-42 352-38 138 4 226 44 372 40 96-3 178-18 314-40v140H0Z"
          className="fill-primary/10"
        />
        <path
          d="M0 156c186-30 300 10 452 4 152-6 236-34 392-26 156 8 300 38 440 22 60-7 108-14 156-24v108H0Z"
          className="fill-primary/[0.16]"
        />

        {/* Tractor works the ridge line of the middle hill, left to right. */}
        <g
          style={{
            ['--from' as string]: '-12%',
            ['--to' as string]: '110%',
            animation: 'cross 30s linear -6s infinite',
          }}
        >
          <Tractor />
        </g>

        {/* ------------------------------------------------- near field + crop */}
        <path
          d="M0 196c180-22 320 6 520 2s320-24 500-16c140 6 280 20 420 12v46H0Z"
          className="fill-primary/25"
        />

        <g className="fill-primary/45 stroke-primary/45">
          {STALKS.map((stalk) => (
            <g
              key={stalk.x}
              className="origin-base"
              style={{
                animation: `sway ${stalk.duration}s ease-in-out ${stalk.delay}s infinite`,
              }}
            >
              <path
                d={`M${stalk.x} 240V${240 - stalk.height}`}
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
              {stalk.ear ? (
                <ellipse cx={stalk.x} cy={240 - stalk.height - 5} rx="3.2" ry="7" stroke="none" />
              ) : (
                <>
                  <path
                    d={`M${stalk.x} ${240 - stalk.height + 9}c-7-2-10-7-10-13 6 0 10 5 10 13Z`}
                    stroke="none"
                  />
                  <path
                    d={`M${stalk.x} ${240 - stalk.height + 3}c7-2 11-8 11-15-7 1-11 7-11 15Z`}
                    stroke="none"
                  />
                </>
              )}
            </g>
          ))}
        </g>
      </svg>

      {MOTES.map((mote) => (
        <span
          key={mote.left}
          className="absolute bottom-6 rounded-full bg-accent/55"
          style={{
            left: `${mote.left}%`,
            width: mote.size,
            height: mote.size,
            ['--mote-x' as string]: `${mote.drift}px`,
            animation: `mote ${mote.duration}s linear ${mote.delay}s infinite`,
          }}
        />
      ))}

      {/* Furrows crawling toward the viewer under the crop — the one thing here
          that suggests a moving camera rather than a moving subject. */}
      <div className="soil-rows absolute inset-x-0 bottom-0 h-16 opacity-50" />

      {/* Fades the band into whatever section follows. */}
      <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-b from-transparent to-background" />
    </div>
  )
}

function Tractor() {
  return (
    <g transform="translate(0 168) scale(0.9)" className="fill-primary/55">
      {/* Exhaust, puffing on a loop offset from the wheels. */}
      {[0, 1, 2].map((i) => (
        <circle
          key={i}
          cx="-22"
          cy="-40"
          r="3.5"
          className="origin-self fill-primary/30"
          style={{ animation: `puff 2.4s ease-out ${i * 0.8}s infinite` }}
        />
      ))}
      <rect x="-24" y="-40" width="5" height="16" rx="2" />

      {/* Cab and body. */}
      <path d="M-4-40h17c2 0 3 1 3 3v14H-4Z" />
      <path d="M-30-24h50c3 0 5 2 5 5v11H-30Z" />
      <rect x="20" y="-16" width="14" height="7" rx="2" />

      {/* Rear wheel, with spokes so the rotation is legible. */}
      <g className="origin-self" style={{ animation: 'wheel 2.6s linear infinite' }}>
        <circle cx="-16" cy="-13" r="13" />
        <circle cx="-16" cy="-13" r="6" className="fill-background/70" />
        <path
          d="M-16-26v26M-29-13h26M-25-22l18 18M-7-22l-18 18"
          className="stroke-primary/55"
          strokeWidth="1.6"
          fill="none"
        />
      </g>

      {/* Front wheel turns faster — it is the smaller one. */}
      <g className="origin-self" style={{ animation: 'wheel 1.5s linear infinite' }}>
        <circle cx="22" cy="-7" r="7" />
        <circle cx="22" cy="-7" r="3" className="fill-background/70" />
      </g>
    </g>
  )
}
