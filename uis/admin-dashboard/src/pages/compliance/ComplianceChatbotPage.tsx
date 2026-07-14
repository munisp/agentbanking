import React, { useEffect, useRef, useState } from "react";
import { MessageCircle, Send, Bot, User, Search, Shield, CheckCircle, BookOpen, RefreshCw } from "lucide-react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const QUICK_CHECKS = [
  { key: "kyc", label: "KYC", status: "compliant", details: "All KYC tiers configured. Tier 1 allows ₦50k/day, Tier 2 ₦200k/day, Tier 3 ₦5M/day.", requirements: ["BVN linkage required", "NIN for Tier 3", "Liveness check enabled"] },
  { key: "aml", label: "AML", status: "compliant", details: "AML monitoring active. Transaction velocity checks, PEP screening, and SCUML reporting enabled.", requirements: ["STR filing enabled", "CTR threshold ₦5M", "Sanctions list updated 2025-01-10"] },
  { key: "transaction_limit", label: "Transaction Limits", status: "review_needed", details: "Daily limits approaching CBN guidance update. Review expected changes for 2025.", requirements: ["Max single txn ₦1M", "Daily limit by tier", "Monthly review required"] },
  { key: "agent_onboarding", label: "Agent Onboarding", status: "compliant", details: "Agent onboarding meets CBN guidelines. Training completion > 95%.", requirements: ["CAC registration", "Guarantor required", "Physical verification done"] },
  { key: "reporting", label: "Reporting", status: "compliant", details: "All mandatory reports filed. CBN monthly return, NDPR quarterly summary up to date.", requirements: ["CBN returns: filed", "NDPR quarterly: filed", "SCUML monthly: filed"] },
];

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const SUGGESTED = ["What are CBN agent banking limits?", "How does fraud detection work?", "KYC tier requirements", "AML compliance checklist"];

export default function ComplianceChatbotPage() {
  const [tab, setTab] = useState<"chat" | "kb" | "checks">("chat");
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Hello! I'm the Compliance Assistant. Ask me about CBN regulations, KYC requirements, AML compliance, agent onboarding, fraud patterns, and more.", timestamp: new Date() }
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [kbQuery, setKbQuery] = useState("");
  const [kbResults, setKbResults] = useState<any[]>([]);
  const [kbLoading, setKbLoading] = useState(false);
  const [activeCheck, setActiveCheck] = useState(QUICK_CHECKS[0]);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || sending) return;
    const userMsg: Message = { role: "user", content: input.trim(), timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setSending(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/chatbot/message`, {
        method: "POST",
        headers: { ...getTenantHeadersFromStorage(), "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg.content }),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, { role: "assistant", content: data.reply || data.message, timestamp: new Date() }]);
      } else {
        setMessages(prev => [...prev, { role: "assistant", content: "I'm currently unavailable. Please check the compliance documentation or contact the compliance team.", timestamp: new Date() }]);
      }
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Connection error. Please try again.", timestamp: new Date() }]);
    } finally { setSending(false); }
  };

  const searchKb = async () => {
    if (!kbQuery.trim()) return;
    setKbLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/compliance/api/v1/knowledge-base/search?q=${encodeURIComponent(kbQuery)}&topK=5`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) setKbResults((await res.json()).results ?? []);
      else setKbResults([
        { id: "1", title: "CBN Agent Banking Guidelines 2023", category: "CBN", relevance: 0.95, content: "CBN circular outlining agent banking requirements, float limits, and POS terminal management guidelines." },
        { id: "2", title: "KYC Tiered Framework", category: "KYC", relevance: 0.87, content: "Three-tier KYC system: Tier 1 (BVN only), Tier 2 (BVN + address), Tier 3 (full documentation)." },
        { id: "3", title: "AML/CFT Compliance Manual", category: "AML", relevance: 0.82, content: "Anti-Money Laundering procedures, STR filing requirements, and suspicious transaction identification." },
      ]);
    } catch { setKbResults([]); }
    finally { setKbLoading(false); }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><MessageCircle className="h-7 w-7 text-purple-600" />Compliance Chatbot</h1>
          <p className="text-gray-500 text-sm mt-1">Natural language queries for compliance, fraud patterns, and regulations</p>
        </div>
      </div>

      <div className="flex border-b border-gray-200 gap-1">
        {[{ key: "chat", label: "Chat" }, { key: "kb", label: "Knowledge Base" }, { key: "checks", label: "Quick Checks" }].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)} className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${tab === t.key ? "border-purple-600 text-purple-600" : "border-transparent text-gray-500 hover:text-gray-700"}`}>{t.label}</button>
        ))}
      </div>

      {tab === "chat" && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm flex flex-col" style={{ height: "calc(100vh - 320px)", minHeight: "400px" }}>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "assistant" && (
                  <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center shrink-0 mt-1">
                    <Bot className="h-4 w-4 text-purple-600" />
                  </div>
                )}
                <div className={`max-w-[75%] rounded-xl p-3 text-sm ${msg.role === "user" ? "bg-purple-600 text-white" : "bg-gray-100 text-gray-800"}`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  <p className={`text-xs mt-1 ${msg.role === "user" ? "text-purple-200" : "text-gray-400"}`}>{msg.timestamp.toLocaleTimeString()}</p>
                </div>
                {msg.role === "user" && (
                  <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center shrink-0 mt-1">
                    <User className="h-4 w-4 text-white" />
                  </div>
                )}
              </div>
            ))}
            {sending && (
              <div className="flex gap-3 justify-start">
                <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center shrink-0"><Bot className="h-4 w-4 text-purple-600" /></div>
                <div className="bg-gray-100 rounded-xl p-3"><RefreshCw className="h-4 w-4 animate-spin text-gray-400" /></div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="p-4 border-t border-gray-100">
            <div className="flex flex-wrap gap-2 mb-3">
              {SUGGESTED.map(q => (
                <button key={q} onClick={() => setInput(q)} className="text-xs px-3 py-1 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full transition-colors">{q}</button>
              ))}
            </div>
            <div className="flex gap-2">
              <input className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500" placeholder="Ask about compliance, fraud patterns, regulations..." value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()} disabled={sending} />
              <button onClick={sendMessage} disabled={sending || !input.trim()} className="p-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50 transition-colors">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {tab === "kb" && (
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
            <h2 className="font-semibold text-gray-800 mb-3 flex items-center gap-2"><Search className="h-4 w-4" />Knowledge Base Search</h2>
            <div className="flex gap-2">
              <input className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Search compliance knowledge base..." value={kbQuery} onChange={e => setKbQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && searchKb()} />
              <button onClick={searchKb} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm">Search</button>
            </div>
          </div>
          {kbLoading && <div className="text-center py-8 text-gray-400"><RefreshCw className="w-6 h-6 animate-spin mx-auto" /></div>}
          {kbResults.map(r => (
            <div key={r.id} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-800">{r.title}</h4>
                <div className="flex gap-2">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">{r.category}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">{(r.relevance * 100).toFixed(0)}% match</span>
                </div>
              </div>
              <p className="text-sm text-gray-500">{r.content}</p>
            </div>
          ))}
        </div>
      )}

      {tab === "checks" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="space-y-2">
            <h2 className="font-semibold text-gray-800 flex items-center gap-2"><Shield className="h-4 w-4" />Check Type</h2>
            {QUICK_CHECKS.map(c => (
              <button key={c.key} onClick={() => setActiveCheck(c)} className={`w-full text-left px-4 py-3 rounded-xl border text-sm transition-colors ${activeCheck.key === c.key ? "border-blue-500 bg-blue-50 text-blue-700 font-medium" : "border-gray-200 bg-white hover:bg-gray-50 text-gray-700"}`}>{c.label}</button>
            ))}
          </div>
          <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              {activeCheck.status === "compliant"
                ? <CheckCircle className="h-8 w-8 text-emerald-500" />
                : <Shield className="h-8 w-8 text-amber-500" />
              }
              <div>
                <h3 className="font-semibold text-gray-900">{activeCheck.label}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${activeCheck.status === "compliant" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>{activeCheck.status.replace(/_/g, " ")}</span>
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-4">{activeCheck.details}</p>
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase mb-2">Requirements</p>
              <ul className="space-y-2">
                {activeCheck.requirements.map((r, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-gray-600">
                    <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0" /><span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
