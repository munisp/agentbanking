import { MessageSquare, Star, RefreshCw, TrendingUp, TrendingDown, Minus, Send, CheckCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const CustomerFeedback = () => {
  const { user } = useAuth();
  const [feedback, setFeedback] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showSurvey, setShowSurvey] = useState(false);
  const [surveyPhone, setSurveyPhone] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [period, setPeriod] = useState("30");

  useEffect(() => {
    if (!user?.keycloakId) return;
    fetchFeedback();
    fetchStats();
  }, [period, user]);

  const fetchStats = async () => {
    const keycloakId = user?.keycloakId;
    if (!keycloakId) return;
    try {
      const res = await fetch(`${CORE_BANKING_URL}/agent/api/v1/feedback/stats/${keycloakId}?days=${period}`, { headers: authHeaders() });
      if (res.ok) setStats(await res.json());
    } catch { }
  };

  const fetchFeedback = async () => {
    const keycloakId = user?.keycloakId;
    if (!keycloakId) return;
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/agent/api/v1/feedback/${keycloakId}?days=${period}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        setFeedback(Array.isArray(data.feedback) ? data.feedback : Array.isArray(data) ? data : []);
      }
    } catch { setFeedback([]); }
    finally { setLoading(false); }
  };

  const sendNpsSurvey = async () => {
    if (!surveyPhone || !user?.keycloakId) return;
    setSending(true);
    try {
      const keycloakId = user?.keycloakId;
      const res = await fetch(`${CORE_BANKING_URL}/agent/api/v1/feedback/nps/send`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: keycloakId, customer_phone: surveyPhone }),
      });
      if (!res.ok) throw new Error("Failed to send survey");
      setSent(true);
      setSurveyPhone("");
      setTimeout(() => { setSent(false); setShowSurvey(false); }, 3000);
    } catch (err) { alert(err.message); }
    finally { setSending(false); }
  };

  const npsScore = stats?.nps_score ?? null;
  const npsColor = npsScore === null ? "text-gray-400" : npsScore >= 50 ? "text-emerald-400" : npsScore >= 0 ? "text-yellow-400" : "text-red-400";
  const NpsTrendIcon = npsScore === null ? Minus : npsScore >= 50 ? TrendingUp : npsScore >= 0 ? Minus : TrendingDown;

  const ratingStars = (rating) => Array.from({ length: 5 }, (_, i) => (
    <Star key={i} className={`w-3 h-3 ${i < (rating || 0) ? "text-yellow-400 fill-yellow-400" : "text-gray-600"}`} />
  ));

  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-600/20 rounded-lg"><MessageSquare className="w-6 h-6 text-yellow-400" /></div>
            <div>
              <h1 className="text-2xl font-bold">Customer Feedback</h1>
              <p className="text-gray-400 text-sm">NPS surveys and customer satisfaction tracking</p>
            </div>
          </div>
          <div className="flex gap-2">
            {["7", "30", "90"].map(p => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${period === p ? "bg-blue-600 text-white" : "bg-gray-50 text-gray-400 hover:bg-gray-700"}`}>
                {p}d
              </button>
            ))}
            <button onClick={() => setShowSurvey(true)} className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 rounded-lg text-sm font-medium transition-colors">
              <Send className="w-4 h-4" /> Send Survey
            </button>
          </div>
        </div>

        {/* NPS Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "NPS Score", value: npsScore !== null ? npsScore : "N/A", color: npsColor },
            { label: "Responses", value: stats?.total_responses ?? "—", color: "text-blue-400" },
            { label: "Promoters", value: stats?.promoters ?? "—", color: "text-emerald-400" },
            { label: "Detractors", value: stats?.detractors ?? "—", color: "text-red-400" },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-gray-100 border border-gray-200 rounded-xl p-4">
              <p className="text-xs text-gray-400">{label}</p>
              <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
            </div>
          ))}
        </div>

        {/* Rating Distribution */}
        {stats?.rating_distribution && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5">
            <h3 className="font-medium text-sm text-gray-600 mb-3">Rating Distribution</h3>
            <div className="space-y-2">
              {[5, 4, 3, 2, 1].map(r => {
                const count = stats.rating_distribution[r] || 0;
                const total = stats.total_responses || 1;
                const pct = (count / total) * 100;
                return (
                  <div key={r} className="flex items-center gap-3">
                    <div className="flex items-center gap-0.5">{ratingStars(r)}</div>
                    <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div className="h-full bg-yellow-500 rounded-full" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-xs text-gray-400 w-8 text-right">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Send Survey Modal */}
        {showSurvey && (
          <div className="bg-gray-100 border border-gray-200 rounded-xl p-5">
            {sent ? (
              <div className="text-center py-4">
                <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
                <p className="font-medium text-emerald-300">Survey sent successfully!</p>
              </div>
            ) : (
              <>
                <h2 className="font-semibold mb-3">Send NPS Survey</h2>
                <p className="text-xs text-gray-400 mb-3">Customer will receive an SMS with a 0–10 rating survey</p>
                <div className="flex gap-2">
                  <input value={surveyPhone} onChange={e => setSurveyPhone(e.target.value)} placeholder="Customer phone (e.g. +2348...)"
                    className="flex-1 bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-yellow-500" />
                  <button onClick={sendNpsSurvey} disabled={sending || !surveyPhone}
                    className="px-4 py-2 bg-yellow-600 hover:bg-yellow-700 disabled:opacity-50 rounded-lg text-sm font-medium flex items-center gap-1 transition-colors">
                    {sending ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                    {sending ? "Sending..." : "Send"}
                  </button>
                  <button onClick={() => setShowSurvey(false)} className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition-colors">Cancel</button>
                </div>
              </>
            )}
          </div>
        )}

        {/* Feedback List */}
        <div className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h3 className="font-medium flex items-center gap-2"><MessageSquare className="w-4 h-4 text-gray-400" /> Recent Feedback</h3>
            <button onClick={fetchFeedback} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"><RefreshCw className="w-3 h-3" /> Refresh</button>
          </div>
          {loading ? (
            <div className="p-8 text-center text-gray-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto" /></div>
          ) : feedback.length === 0 ? (
            <div className="p-10 text-center text-gray-500">
              <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>No feedback received yet</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {feedback.map((fb, i) => (
                <li key={fb.id || i} className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <div className="flex">{ratingStars(fb.rating)}</div>
                        <span className={`text-xs font-medium ${fb.nps_score >= 9 ? "text-emerald-400" : fb.nps_score >= 7 ? "text-yellow-400" : "text-red-400"}`}>
                          {fb.nps_score !== undefined ? `NPS: ${fb.nps_score}/10` : ""}
                        </span>
                      </div>
                      {fb.comment && <p className="text-sm text-gray-600 italic">"{fb.comment}"</p>}
                      <p className="text-xs text-gray-500 mt-1">{new Date(fb.created_at || Date.now()).toLocaleDateString()}</p>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${fb.nps_score >= 9 ? "bg-emerald-900/30 text-emerald-400" : fb.nps_score >= 7 ? "bg-yellow-900/30 text-yellow-400" : "bg-red-900/30 text-red-400"}`}>
                      {fb.nps_score >= 9 ? "Promoter" : fb.nps_score >= 7 ? "Passive" : "Detractor"}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default CustomerFeedback;
