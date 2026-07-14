import React, { createContext, useContext, useEffect, useState } from "react";
import { flushPendingTransfers } from "../services/offlineTransferQueue";
import {
  addNetworkListener,
  isDeviceOnline,
  startNetworkMonitor,
  stopNetworkMonitor,
} from "../services/networkService";

const NetworkContext = createContext({ isOnline: true });

export function NetworkProvider({ children }) {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    isDeviceOnline().then(setIsOnline);

    const remove = addNetworkListener(({ isOnline: nowOnline, wasOnline }) => {
      setIsOnline(nowOnline);
      if (!wasOnline && nowOnline) {
        // Network restored (SIM failover completed) — drain the offline queue
        flushPendingTransfers(async (kind, payload) => {
          const { transactionService } = require("../services/transactionService");
          await transactionService.sendTransferOnline(kind, payload);
        }).catch(() => {});
      }
    });

    startNetworkMonitor();
    return () => {
      remove();
      stopNetworkMonitor();
    };
  }, []);

  return (
    <NetworkContext.Provider value={{ isOnline }}>
      {children}
    </NetworkContext.Provider>
  );
}

export function useNetwork() {
  return useContext(NetworkContext);
}
