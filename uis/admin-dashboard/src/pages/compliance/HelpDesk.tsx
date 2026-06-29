import { Ticket, Plus, X, MessageSquare, ChevronRight, Clock } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_SUPPORT_COMMS_URL || import.meta.env.VITE_API_URL || "http://localhost:8011";

interface TicketItem {
  id: string;
  title: string;
  requester: string;
  priority: "Critical" | "High" | "Medium" | "Low";
  category: "Technical" | "Billing" | "Compliance" | "Training";
  status: "Open" | "In Progress" | "Resolved" | "Escalated";
  created: string;
  slaDeadline: string;
  assignee: string;
  comments: { author: string; text: string; time: string }[];
}

const MOCK_TICKETS: TicketItem[] = [
  { id: "TKT-001", title: "USSD transactions failing for MTN subscribers", requester: "Tunde Adebisi", priority: "Critical", category: "Technical", status: "Open", created: "2026-05-01", slaDeadline: "2026-05-02", assignee: "DevOps Team", comments: [{ author: "Tunde Adebisi", text: "Multiple agent complaints since 8am.", time: "08:15" }] },
  { id: "TKT-002", title: "Commission payout discrepancy for April", requester: "Amaka Okonkwo", priority: "High", category: "Billing", status: "In Progress", created: "2026-04-30", slaDeadline: "2026-05-03", assignee: "Finance Team", comments: [{ author: "Finance Team", text: "Investigating ledger entries.", time: "14:00" }] },
  { id: "TKT-003", title: "New agent KYC training materials needed", requester: "Seun Lawson", priority: "Medium", category: "Training", status: "Open", created: "2026-04-29", slaDeadline: "2026-05-06", assignee: "Training Team", comments: [] },
  { id: "TKT-004", title: "AML flag on agent TXN-992 incorrect", requester: "Bayo Adeyemi", priority: "High", category: "Compliance", status: "Escalated", created: "2026-04-28", slaDeadline: "2026-04-30", assignee: "Compliance Team", comments: [{ author: "Compliance Team", text: "Escalated to CBN liaison for review.", time: "09:30" }] },
  { id: "TKT-005", title: "POS terminal sync issue", requester: "Ngozi Eze", priority: "Low", category: "Technical", status: "Resolved", created: "2026-04-25", slaDeadline: "2026-04-28", assignee: "Support Team", comments: [{ author: "Support Team", text: "Resolved after firmware update.", time: "16:45" }] },
];

const PRIORITY_STYLES: Record<string, string> = {
  Critical: "bg-red-100 text-red-700",
  High: "bg-orange-100 text-orange-700",
  Medium: "bg-amber-100 text-amber-700",
  Low: "bg-gray-100 text-gray-600",
};

const TABS = ["Open", "In Progress", "Resolved", "Escalated"] as const;
type Tab = typeof TABS[number];

const HelpDesk: React.FC = () => {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("Open");
  const [loading, setLoading] = useState(false);
  const [drawerTicket, setDrawerTicket] = useState<TicketItem | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: "", requester: "", priority: "Medium", category: "Technical" });
  const [comment, setComment] = useState("");

  useEffect(() => { fetchTickets(); }, []);

  const fetchTickets = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/support/api/v1/helpdesk/tickets`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setTickets(Array.isArray(d.tickets) ? d.tickets : MOCK_TICKETS); }
      else { setTickets(MOCK_TICKETS); }
    } catch { setTickets(MOCK_TICKETS); }
    finally { setLoading(false); }
  };

  const isSLABreached = (deadline: string) => new Date(deadline) < new Date();
  const filtered = tickets.filter(t => t.status === activeTab);

  const submitTicket = async () => {
    const newTicket: TicketItem = {
      id: `TKT-${Date.now()}`, title: form.title, requester: form.requester,
      priority: form.priority as TicketItem["priority"], category: form.category as TicketItem["category"],
      status: "Open", created: new Date().toISOString().split("T")[0],
      slaDeadline: new Date(Date.now() + 3 * 86400000).toISOString().split("T")[0],
      assignee: "Unassigned", comments: [],
    };
    try {
      await fetch(`${CORE_URL}/support/api/v1/helpdesk/tickets`, {
        method: "POST", headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
    } catch { }
    setTickets(t => [newTicket, ...t]);
    setShowForm(false);
    setForm({ title: "", requester: "", priority: "Medium", category: "Technical" });
  };

  const addComment = () => {
    if (!comment.trim() || !drawerTicket) return;
    const newComment = { author: "Admin", text: comment.trim(), time: new Date().toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" }) };
    setTickets(ts => ts.map(t => t.id === drawerTicket.id ? { ...t, comments: [...t.comments, newComment] } : t));
    setDrawerTicket(prev => prev ? { ...prev, comments: [...prev.comments, newComment] } : prev);
    setComment("");
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Ticket className="w-7 h-7 text-indigo-600" /> Help Desk
          </h1>
          <p className="text-gray-500 text-sm mt-1">Track, triage and resolve support tickets</p>
        </div>
        <button onClick={() => setShowForm(true)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">
          <Plus className="w-4 h-4" /> Create Ticket
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-4">
          <h2 className="font-semibold text-gray-800">New Ticket</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Title</label>
              <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Requester</label>
              <input value={form.requester} onChange={e => setForm(f => ({ ...f, requester: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Priority</label>
              <select value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {["Critical", "High", "Medium", "Low"].map(p => <option key={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Category</label>
              <select value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                {["Technical", "Billing", "Compliance", "Training"].map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={submitTicket} className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium">Submit</button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">Cancel</button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6">
        <div className="flex gap-1 mb-5 border-b border-gray-100">
          {TABS.map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${activeTab === tab ? "text-indigo-600 border-b-2 border-indigo-600" : "text-gray-500 hover:text-gray-700"}`}>
              {tab} <span className="ml-1 text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-full">{tickets.filter(t => t.status === tab).length}</span>
            </button>
          ))}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["ID", "Title", "Requester", "Priority", "Category", "Created", "SLA Deadline", "Assignee", ""].map(h => (
                  <th key={h} className="text-left text-xs text-gray-500 font-medium pb-3 pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map(ticket => (
                <tr key={ticket.id} className="hover:bg-gray-50">
                  <td className="py-3 pr-4 text-xs font-mono text-gray-500">{ticket.id}</td>
                  <td className="py-3 pr-4 font-medium text-gray-900 max-w-xs truncate">{ticket.title}</td>
                  <td className="py-3 pr-4 text-gray-600">{ticket.requester}</td>
                  <td className="py-3 pr-4"><span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_STYLES[ticket.priority]}`}>{ticket.priority}</span></td>
                  <td className="py-3 pr-4 text-gray-600">{ticket.category}</td>
                  <td className="py-3 pr-4 text-gray-500">{ticket.created}</td>
                  <td className={`py-3 pr-4 text-sm font-medium flex items-center gap-1 ${isSLABreached(ticket.slaDeadline) ? "text-red-600" : "text-gray-600"}`}>
                    {isSLABreached(ticket.slaDeadline) && <Clock className="w-3 h-3" />}{ticket.slaDeadline}
                  </td>
                  <td className="py-3 pr-4 text-gray-500">{ticket.assignee}</td>
                  <td className="py-3">
                    <button onClick={() => setDrawerTicket(ticket)} className="p-1 hover:bg-gray-100 rounded text-gray-400 hover:text-gray-600">
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={9} className="py-8 text-center text-gray-400 text-sm">No {activeTab.toLowerCase()} tickets</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {drawerTicket && (
        <div className="fixed inset-0 bg-black/30 z-50 flex justify-end" onClick={() => setDrawerTicket(null)}>
          <div className="w-full max-w-md bg-white h-full overflow-y-auto shadow-xl p-6 space-y-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-mono text-gray-400">{drawerTicket.id}</p>
                <h2 className="font-semibold text-gray-900 text-lg mt-1">{drawerTicket.title}</h2>
              </div>
              <button onClick={() => setDrawerTicket(null)} className="p-1 hover:bg-gray-100 rounded"><X className="w-5 h-5 text-gray-500" /></button>
            </div>
            <div className="flex gap-2 flex-wrap">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_STYLES[drawerTicket.priority]}`}>{drawerTicket.priority}</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">{drawerTicket.category}</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{drawerTicket.status}</span>
            </div>
            <div className="text-sm space-y-1 text-gray-600">
              <p>Requester: <strong>{drawerTicket.requester}</strong></p>
              <p>Assignee: <strong>{drawerTicket.assignee}</strong></p>
              <p>Created: {drawerTicket.created} · SLA: <span className={isSLABreached(drawerTicket.slaDeadline) ? "text-red-600 font-semibold" : ""}>{drawerTicket.slaDeadline}</span></p>
            </div>
            <div>
              <h3 className="font-semibold text-sm text-gray-800 mb-3 flex items-center gap-1"><MessageSquare className="w-4 h-4" /> Comments</h3>
              <div className="space-y-3">
                {drawerTicket.comments.map((c, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-gray-700">{c.author}</span>
                      <span className="text-xs text-gray-400">{c.time}</span>
                    </div>
                    <p className="text-sm text-gray-600">{c.text}</p>
                  </div>
                ))}
                {drawerTicket.comments.length === 0 && <p className="text-sm text-gray-400">No comments yet.</p>}
              </div>
              <div className="mt-4 flex gap-2">
                <input value={comment} onChange={e => setComment(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && addComment()}
                  placeholder="Add a comment..."
                  className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                <button onClick={addComment} className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm">Send</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HelpDesk;
