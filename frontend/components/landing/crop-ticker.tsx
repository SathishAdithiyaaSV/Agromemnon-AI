import {
  Carrot,
  CloudRain,
  Leaf,
  Sprout,
  Sun,
  Sunrise,
  Tractor,
  TreeDeciduous,
  Wheat,
} from 'lucide-react'

/**
 * A strip of crops and seasons drifting past, the way a mandi board scrolls.
 *
 * No prices: the landing page must not imply a live feed it is not showing. The
 * track is rendered twice and shifted by exactly half its width, which is what
 * makes the loop seamless — see the `marquee` keyframe.
 */

const ITEMS = [
  { icon: Wheat, label: 'Wheat' },
  { icon: Sprout, label: 'Paddy' },
  { icon: Leaf, label: 'Sugarcane' },
  { icon: Sun, label: 'Kharif' },
  { icon: Carrot, label: 'Groundnut' },
  { icon: CloudRain, label: 'Monsoon sowing' },
  { icon: TreeDeciduous, label: 'Arecanut' },
  { icon: Wheat, label: 'Ragi' },
  { icon: Sunrise, label: 'Rabi' },
  { icon: Tractor, label: 'Soil health' },
  { icon: Leaf, label: 'Cotton' },
  { icon: Sprout, label: 'Tur dal' },
] as const

function Track({ ariaHidden }: { ariaHidden?: boolean }) {
  return (
    <ul className="flex shrink-0 items-center gap-10 px-5" aria-hidden={ariaHidden || undefined}>
      {ITEMS.map((item, index) => (
        <li
          key={`${item.label}-${index}`}
          className="flex items-center gap-2.5 whitespace-nowrap text-sm text-muted-foreground"
        >
          <item.icon className="size-4 text-primary/70" strokeWidth={1.7} />
          {item.label}
        </li>
      ))}
    </ul>
  )
}

export function CropTicker() {
  return (
    <div
      className="relative flex overflow-hidden border-y border-border bg-card/40 py-3.5 [mask-image:linear-gradient(90deg,transparent,black_8%,black_92%,transparent)]"
      aria-label="Crops and seasons Agromemnon covers"
    >
      <div className="flex w-max" style={{ animation: 'marquee 46s linear infinite' }}>
        <Track />
        <Track ariaHidden />
      </div>
    </div>
  )
}
