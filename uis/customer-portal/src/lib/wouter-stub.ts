// Wouter stub — customer-portal uses react-router-dom, not wouter.
// NF-Q-1: JSX converted to React.createElement so this stays a valid .ts module.
import React from "react";
export const useLocation = () => [window.location.pathname, () => {}] as const;
export const useRoute = (_pattern: string) => [false, {}] as const;
export const Link = ({ href, children, ...props }: any) => {
  const { default: RouterLink } = require("react-router-dom");
  return RouterLink
    ? React.createElement(RouterLink.Link, { to: href, ...props }, children)
    : React.createElement("a", { href, ...props }, children);
};
export const Route = () => null;
export const Switch = ({ children }: any) => children;
export const Router = ({ children }: any) => children;
