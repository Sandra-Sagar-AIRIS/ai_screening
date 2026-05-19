import * as React from "react";
import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost";
  /** "sm" reduces height to h-8 and uses text-xs padding */
  size?: "default" | "sm" | "lg" | "icon";
};

export function Button({ className, variant = "default", size = "default", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        // size variants
        size === "default" && "h-10 px-4 text-sm",
        size === "sm"      && "h-8 px-3 text-xs",
        size === "lg"      && "h-11 px-6 text-base",
        size === "icon"    && "h-9 w-9",
        // colour variants
        variant === "default" && "bg-slate-900 text-white hover:bg-slate-700",
        variant === "outline" && "border border-slate-300 bg-white hover:bg-slate-100",
        variant === "ghost"   && "hover:bg-slate-100",
        className
      )}
      {...props}
    />
  );
}
