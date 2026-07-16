import React, { createContext, useContext } from "react";
import { useOfflineStore } from "../hooks/useOfflineStore";
import { useOfflineTransaction } from "../hooks/useOfflineTransaction";

/**
 * Offline Context
 * Provides offline transaction capabilities throughout the app
 */
const OfflineContext = createContext(null);

export const OfflineProvider = ({ children }) => {
  const offlineStore = useOfflineStore();
  const offlineTransaction = useOfflineTransaction();

  const value = {
    ...offlineStore,
    ...offlineTransaction,
  };

  return (
    <OfflineContext.Provider value={value}>
      {children}
    </OfflineContext.Provider>
  );
};

export const useOffline = () => {
  const context = useContext(OfflineContext);
  if (!context) {
    throw new Error(
      "useOffline must be used within OfflineProvider"
    );
  }
  return context;
};

export default OfflineContext;
