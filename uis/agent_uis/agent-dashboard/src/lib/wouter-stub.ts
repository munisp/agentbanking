import { useNavigate, useLocation as useReactLocation } from "react-router-dom";

export function useLocation(): [string, (path: string) => void] {
  const navigate = useNavigate();
  const location = useReactLocation();
  return [location.pathname, (path: string) => navigate(path)];
}
