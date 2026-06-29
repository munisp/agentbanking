import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { simOrchestratorApi } from "../services/apiService";

const SIMStatusContext = createContext(null);

const POLL_INTERVAL_MS = 15_000;

export function SIMStatusProvider({ children }) {
  const [status, setStatus] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const poll = async () => {
      const data = await simOrchestratorApi.getStatus();
      if (data) setStatus(data);
    };
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  return (
    <SIMStatusContext.Provider value={status}>
      {children}
    </SIMStatusContext.Provider>
  );
}

export const useSIMStatus = () => useContext(SIMStatusContext);
