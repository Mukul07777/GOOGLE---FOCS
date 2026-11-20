import { Link } from "react-router-dom";
import { Backdrop } from "@/components/Backdrop";
import { LogoMark } from "@/components/common";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="grid min-h-dvh place-items-center px-6 text-center pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
      <Backdrop scene="auth" />
      <div>
        <LogoMark className="mx-auto h-12 w-12" />
        <div className="mt-6 font-serif text-8xl italic text-gradient">404</div>
        <h1 className="mt-2 text-[26px]">This board is blank.</h1>
        <p className="mt-1 text-sm text-muted">The page you're looking for doesn't exist.</p>
        <Link to="/"><Button variant="primary" className="mt-6">Back home</Button></Link>
      </div>
    </div>
  );
}
