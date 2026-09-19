import { Children } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'
import { YouTubeEmbed, youtubeVideoId } from './youtube-embed'

const isBlank = (node: any) =>
  node.type === 'text' ? node.value.trim() === '' : node.tagName === 'br'

/**
 * Index of a leading YouTube link in a paragraph, or -1. The agent writes the link
 * and its one-line reason as one paragraph, so the link is the paragraph's first
 * meaningful child rather than its only child.
 */
function leadingVideoLink(node: any): number {
  const children: any[] = node?.children ?? []
  const index = children.findIndex(
    (child) => child.tagName === 'a' && youtubeVideoId(child.properties?.href),
  )
  return index >= 0 && children.slice(0, index).every(isBlank) ? index : -1
}

/**
 * Renders an agent answer. Tables get their own scroll container: mandi-price and
 * fertilizer replies are wide, and without it they either overflow the bubble or
 * force the whole page sideways. A paragraph led by a YouTube link — what
 * video_tutor appends — becomes an inline player above its caption.
 */
export function MarkdownView({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn('md-body', className)}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ node, ...props }) => (
            <div className="table-scroll">
              <table {...props} />
            </div>
          ),
          p: ({ node, children, ...props }) => {
            const index = leadingVideoLink(node)
            if (index < 0) return <p {...props}>{children}</p>

            const link = (node as any).children[index]
            const videoId = youtubeVideoId(link.properties?.href)!
            const title = link.children?.[0]?.value ?? 'Recommended video'
            const caption = Children.toArray(children).slice(index + 1)
            const hasCaption = caption.some((child) => typeof child !== 'string' || child.trim() !== '')

            return (
              <>
                <YouTubeEmbed videoId={videoId} title={title} />
                {hasCaption ? <p {...props}>{caption}</p> : null}
              </>
            )
          },
          a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {children}
      </Markdown>
    </div>
  )
}
