import React from "react";

type Variant = "default" | "outline" | "destructive" | "ghost" | "link" | "secondary";
type Size = "default" | "sm" | "lg" | "icon" | "xs";

export function Button({
  children,
  onClick,
  disabled,
  variant = "default",
  size = "default",
  className = "",
  type = "button",
  asChild: _asChild,
  ...rest
}: {
  children?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: Variant;
  size?: Size;
  className?: string;
  type?: "button" | "submit" | "reset";
  asChild?: boolean;
  [key: string]: any;
}) {
  const base = "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed";
  const variants: Record<Variant, string> = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 text-gray-700 hover:bg-gray-50",
    destructive: "bg-red-600 text-white hover:bg-red-700",
    ghost: "text-gray-700 hover:bg-gray-100",
    link: "text-blue-600 underline-offset-4 hover:underline",
    secondary: "bg-gray-100 text-gray-700 hover:bg-gray-200",
  };
  const sizes: Record<Size, string> = {
    default: "px-4 py-2 text-sm",
    sm: "px-3 py-1.5 text-xs",
    lg: "px-6 py-3 text-base",
    icon: "p-2 text-sm",
    xs: "px-2 py-1 text-xs",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export default Button;
