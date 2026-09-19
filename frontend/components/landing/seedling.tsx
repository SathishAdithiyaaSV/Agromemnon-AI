/**
 * A seed that germinates: the stem draws itself upward, then the two cotyledons
 * unfurl, and the whole sprout keeps a slow lean afterwards. Used as the visual
 * anchor of the closing call to action.
 *
 * It germinates once and then settles, rather than looping the growth — a plant
 * that un-grows every four seconds reads as a rendering bug. The stem uses
 * `stroke-dashoffset` against a hand-measured dash length, so the path and that
 * number have to change together.
 */
export function Seedling({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 72" fill="none" className={className} aria-hidden>
      {/* Soil line and the mound the stem comes out of — these do not move. */}
      <path
        d="M6 62h52M14 66.5h36"
        className="stroke-primary/35"
        strokeWidth="2.5"
        strokeLinecap="round"
      />

      <g className="origin-base" style={{ animation: 'sway 6s ease-in-out 2.4s infinite' }}>
        <path
          d="M32 62V22"
          className="stroke-primary"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="40"
          style={{
            ['--len' as string]: '40',
            animation: 'draw 1.4s ease-out both',
          }}
        />

        <path
          d="M32 34c-10 0-16-6-16-16 10 0 16 6 16 16Z"
          className="fill-leaf/85"
          style={{
            transformOrigin: '32px 34px',
            animation: 'unfurl 0.8s cubic-bezier(0.22,1,0.36,1) 1s both',
          }}
        />
        <path
          d="M32 28c11 0 18-7 18-18-11 0-18 7-18 18Z"
          className="fill-primary"
          style={{
            transformOrigin: '32px 28px',
            animation: 'unfurl 0.8s cubic-bezier(0.22,1,0.36,1) 1.25s both',
          }}
        />
      </g>
    </svg>
  )
}
