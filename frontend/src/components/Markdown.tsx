// Its own file so the markdown and LaTeX libraries (~130 KB gzipped) load with the pages that show notes, not the first page.
import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { ScrollX } from "@/components/ScrollX";
import { normalizeMath, repairTables } from "@/lib/math";
import { rehypeMathGuard } from "@/lib/mathGuard";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- Markdown with LaTeX */
// a table never spills out of the place it is shown in (a chat bubble, a phone): it slides sideways there
const MD_COMPONENTS: Components = {
  table: ({ node: _node, ...props }) => <ScrollX hint className="md-table"><table {...props} /></ScrollX>,
};

export const Markdown = memo(function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("prose-notes", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeMathGuard, [rehypeKatex, { throwOnError: false, strict: false }]]}
        components={MD_COMPONENTS}>
        {repairTables(normalizeMath(children || ""))}
      </ReactMarkdown>
    </div>
  );
});
