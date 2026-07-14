// Wouter stub — customer-portal uses react-router-dom, not wouter.
export const useLocation = () => [window.location.pathname, () => {}] as const;
export const useRoute = (_pattern: string) => [false, {}] as const;
export const Link = ({ href, children, ...props }: any) => {
  const { default: RouterLink } = require("react-router-dom");
  return RouterLink ? <RouterLink.Link to={href} {...props}>{children}</RouterLink.Link> : <a href={href} {...props}>{children}</a>;
};
export const Route = () => null;
export const Switch = ({ children }: any) => children;
export const Router = ({ children }: any) => children;
