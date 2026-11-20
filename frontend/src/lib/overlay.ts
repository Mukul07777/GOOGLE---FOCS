import { useEffect, useRef } from "react";

/** The phone's Back button closes an open sheet, drawer or search instead of leaving the page under it: while open,
 *  the overlay holds one history entry of its own. */
export function useBackClose(open: boolean, close: () => void) {
  const latest = useRef(close);
  latest.current = close;
  useEffect(() => {
    if (!open) return;
    const id = Math.random().toString(36).slice(2);
    window.history.pushState({ ...window.history.state, focsOverlay: id }, "");
    let viaBack = false;
    const onPop = () => {
      if (window.history.state?.focsOverlay === id) return;  // (an overlay opened on top of this one went)
      viaBack = true;
      latest.current();
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      if (viaBack) return;
      // closed by a button: drop its entry. Later, not now: a link or a redirect in this same render (signing out from
      // the menu) has to land first, and a Back on top of it would undo it. If one did, the entry is no longer on top.
      setTimeout(() => { if (window.history.state?.focsOverlay === id) window.history.back(); }, 0);
    };
  }, [open]);
}
