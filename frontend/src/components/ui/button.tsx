import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "outline" | "danger" | "success";
type Size = "sm" | "md" | "lg" | "icon" | "icon-sm";

/* Both looks of every variant live in index.css: square, wide Jost capitals, solid ink for the primary. */
const variants: Record<Variant, string> = {
  primary: "btn-primary font-semibold",
  secondary: "btn-secondary",
  ghost: "btn-ghost",
  outline: "btn-outline",
  danger: "btn-danger",
  success: "btn-success",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3.5 text-[11px] gap-1.5 rounded-sm pointer-coarse:h-10",
  md: "h-10 px-5 text-[12px] gap-2 rounded-sm",
  lg: "h-12 px-7 text-[12.5px] gap-2.5 rounded-sm",
  icon: "h-10 w-10 rounded-sm",
  "icon-sm": "h-8 w-8 rounded-sm pointer-coarse:h-10 pointer-coarse:w-10",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, icon, className, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "btn inline-flex shrink-0 select-none items-center justify-center font-medium whitespace-nowrap transition-all duration-200 ease-out",
        "disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});
