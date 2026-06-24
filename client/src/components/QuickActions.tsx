/**
 * Quick Actions Bar
 * Context-aware shortcuts for most common agent operations.
 * Expert mode: keyboard shortcuts (Ctrl+1..9)
 * Beginner mode: large labeled buttons with icons
 */
import { useAdaptiveUI, ForExperts, ForBeginners } from "./AdaptiveUI";
import { Banknote, ArrowDownToLine, Phone, Zap, Receipt, Send } from "lucide-react";
import { useLocation } from "wouter";

interface QuickAction {
  label: string;
  icon: React.ReactNode;
  path: string;
  shortcut: string;
  description: string;
}

const ACTIONS: QuickAction[] = [
  { label: "Cash In", icon: <ArrowDownToLine className="w-5 h-5" />, path: "/cash-in", shortcut: "Ctrl+1", description: "Customer deposit" },
  { label: "Cash Out", icon: <Banknote className="w-5 h-5" />, path: "/cash-out", shortcut: "Ctrl+2", description: "Customer withdrawal" },
  { label: "Airtime", icon: <Phone className="w-5 h-5" />, path: "/airtime", shortcut: "Ctrl+3", description: "Airtime top-up" },
  { label: "Transfer", icon: <Send className="w-5 h-5" />, path: "/transfer", shortcut: "Ctrl+4", description: "Money transfer" },
  { label: "Bills", icon: <Zap className="w-5 h-5" />, path: "/bills", shortcut: "Ctrl+5", description: "Bill payments" },
  { label: "Receipt", icon: <Receipt className="w-5 h-5" />, path: "/receipts", shortcut: "Ctrl+6", description: "Reprint receipt" },
];

export function QuickActions() {
  const [, setLocation] = useLocation();
  const { compactMode } = useAdaptiveUI();

  return (
    <div className={`grid gap-2 ${compactMode ? "grid-cols-6" : "grid-cols-3 sm:grid-cols-6"}`}>
      {ACTIONS.map((action) => (
        <button
          key={action.path}
          onClick={() => setLocation(action.path)}
          className={`flex flex-col items-center justify-center rounded-lg border p-3 hover:bg-blue-50 transition-colors dark:hover:bg-blue-900/20 ${
            compactMode ? "p-2" : "p-4"
          }`}
        >
          <div className="text-blue-600 dark:text-blue-400">{action.icon}</div>
          <span className={`mt-1 font-medium ${compactMode ? "text-xs" : "text-sm"}`}>
            {action.label}
          </span>
          <ForBeginners>
            <span className="text-xs text-muted-foreground mt-0.5">{action.description}</span>
          </ForBeginners>
          <ForExperts>
            <span className="text-[10px] text-muted-foreground/60 mt-0.5">{action.shortcut}</span>
          </ForExperts>
        </button>
      ))}
    </div>
  );
}
