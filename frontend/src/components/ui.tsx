import type { ButtonHTMLAttributes, HTMLAttributes, PropsWithChildren } from "react";
import { clsx } from "clsx";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={clsx("card", className)} {...props} />; }
export function Button({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={clsx("button", className)} {...props} />; }
export function Badge({ children, className }: PropsWithChildren<{ className?: string }>) { return <span className={clsx("badge", className)}>{children}</span>; }
export function Spinner() { return <span className="spinner" aria-hidden="true" />; }
