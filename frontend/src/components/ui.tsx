import type { ButtonHTMLAttributes, ComponentProps, PropsWithChildren } from "react";
import { useId } from "react";
import { Info } from "lucide-react";
import { clsx } from "clsx";

export function Card({ className, ...props }: ComponentProps<"div">) { return <div className={clsx("card", className)} {...props} />; }
export function Button({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={clsx("button", className)} {...props} />; }
export function Badge({ children, className }: PropsWithChildren<{ className?: string }>) { return <span className={clsx("badge", className)}>{children}</span>; }
export function Spinner() { return <span className="spinner" aria-hidden="true" />; }
export function InfoTip({ label, children, align = "right" }: PropsWithChildren<{ label: string; align?: "left" | "right" }>) {
  const id = useId();
  return (
    <span className={clsx("metric-info", "info-tip", `tip-${align}`)}>
      <button type="button" aria-label={label} aria-describedby={id}><Info aria-hidden="true" /></button>
      <span role="tooltip" id={id} className="metric-tooltip">{children}</span>
    </span>
  );
}
