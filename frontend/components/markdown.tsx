import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

/**
 * Renders an agent answer. Tables get their own scroll container: mandi-price and
 * fertilizer replies are wide, and without it they either overflow the bubble or
 * force the whole page sideways.
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
          a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {children}
      </Markdown>
    </div>
  )
}
