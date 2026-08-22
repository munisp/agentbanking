/**
 * POS / agent-session store (zustand).
 *
 * Replaces the former 1-line stub. Pages consume it exclusively through
 * selector calls, e.g. `usePosStore(s => s.agent)`, plus a handful of
 * action selectors (`setAgent`, `updateLoyaltyPoints`, `clearFraudCount`).
 */

import { create } from "zustand";

export interface PosAgent {
  id?: number;
  name?: string;
  agentCode?: string;
  role?: string;
  tier?: string;
  rank?: number;
  streak?: number;
  loyaltyPoints?: number;
  floatBalance?: string | number;
  floatLimit?: string | number;
  commissionBalance?: string | number;
  phone?: string;
  email?: string;
  status?: string;
  [key: string]: unknown;
}

export type FraudSeverity = "critical" | "high" | "medium" | "low";

export interface FraudEvent {
  id: string;
  agentCode: string;
  customerName: string;
  type: string;
  amount: number;
  fraudScore: string;
  severity: FraudSeverity;
  reason: string;
  timestamp: string;
  agentName?: string;
  time?: string;
  status?: string;
  [key: string]: unknown;
}

export interface PosChatMessage {
  id?: string | number;
  senderType?: string;
  content?: string;
  text?: string;
  createdAt?: string;
  [key: string]: unknown;
}

export interface PosTransaction {
  id?: string | number;
  amount?: number;
  type?: string;
  status?: string;
  [key: string]: unknown;
}

export interface PosStoreState {
  agent: PosAgent | null;
  agents: PosAgent[];
  transactions: PosTransaction[];
  isConnected: boolean;
  fraudEvents: FraudEvent[];
  unreadFraudCount: number;
  chatMessages: PosChatMessage[];
  setAgent: (agent: PosAgent | null) => void;
  setAgents: (agents: PosAgent[]) => void;
  setTransactions: (transactions: PosTransaction[]) => void;
  setConnected: (isConnected: boolean) => void;
  addFraudEvent: (event: FraudEvent) => void;
  setFraudEvents: (events: FraudEvent[]) => void;
  clearFraudCount: () => void;
  addChatMessage: (message: PosChatMessage) => void;
  setChatMessages: (messages: PosChatMessage[]) => void;
  updateLoyaltyPoints: (delta: number) => void;
  reset: () => void;
}

const initialState = {
  agent: null as PosAgent | null,
  agents: [] as PosAgent[],
  transactions: [] as PosTransaction[],
  isConnected: false,
  fraudEvents: [] as FraudEvent[],
  unreadFraudCount: 0,
  chatMessages: [] as PosChatMessage[],
};

export const usePosStore = create<PosStoreState>()(set => ({
  ...initialState,
  setAgent: agent => set({ agent }),
  setAgents: agents => set({ agents }),
  setTransactions: transactions => set({ transactions }),
  setConnected: isConnected => set({ isConnected }),
  addFraudEvent: event =>
    set(state => ({
      fraudEvents: [event, ...state.fraudEvents],
      unreadFraudCount: state.unreadFraudCount + 1,
    })),
  setFraudEvents: events => set({ fraudEvents: events }),
  clearFraudCount: () => set({ unreadFraudCount: 0 }),
  addChatMessage: message =>
    set(state => ({ chatMessages: [...state.chatMessages, message] })),
  setChatMessages: messages => set({ chatMessages: messages }),
  updateLoyaltyPoints: delta =>
    set(state =>
      state.agent
        ? {
            agent: {
              ...state.agent,
              loyaltyPoints: (Number(state.agent.loyaltyPoints) || 0) + delta,
            },
          }
        : {}
    ),
  reset: () => set(initialState),
}));

export default usePosStore;
