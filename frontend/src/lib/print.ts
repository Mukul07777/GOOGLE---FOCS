import { toast } from "sonner";
import { IN_APP } from "@/lib/server";

/** Print one element on a clean white page (its own window), keeping the app's styles and KaTeX. */
export function printNode(node: HTMLElement, title: string) {
  if (IN_APP) {  // the app has one window and no printer: opening another would replace the app itself
    toast.info("Printing isn't in the app yet. Open Focs in a browser to print this.");
    return;
  }
  const w = window.open("", "_blank", "width=900,height=1000");
  if (!w) return;
  const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style')).map((n) => n.outerHTML).join("");
  w.document.write(`<!doctype html><html data-theme="light"><head><meta charset="utf-8"><title>${title.replace(/</g, "")}</title>${styles}
    <style>body{background:#fff;padding:28px;font-family:"Inter Variable",system-ui,sans-serif}.no-print{display:none!important}
    .print-only{display:block!important}.panel{box-shadow:none!important;break-inside:avoid}
    .md-table{overflow:visible!important;mask-image:none!important}.md-table table{width:100%!important}th,td{max-width:none!important}</style></head><body>${node.innerHTML}</body></html>`);
  w.document.close();
  setTimeout(() => { w.focus(); w.print(); }, 400);
}
