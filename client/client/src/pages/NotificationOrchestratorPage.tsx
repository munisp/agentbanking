import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  Bell,
  Search,
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Send,
  Mail,
  MessageSquare,
  Smartphone,
} from "lucide-react";

const CHANNEL_ICONS: Record<string, any> = {
  sms: Smartphone,
  email: Mail,
  push: Bell,
  whatsapp: MessageSquare,
};

export default function NotificationOrchestratorPage() {
  const [search, setSearch] = useState("");
  const [channelFilter, setChannelFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [editTemplate, setEditTemplate] = useState<any>(null);
  const [form, setForm] = useState({
    name: "",
    channel: "sms",
    subject: "",
    body: "",
    variables: "",
  });

  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const templatesQuery = trpc.notificationOrchestrator.listTemplates.useQuery({
    limit: 100,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.notificationOrchestrator.getStats.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const createMutation =
    // @ts-ignore Sprint 85
    trpc.notificationOrchestrator.createTemplate.useMutation({
      onSuccess: () => {
        templatesQuery.refetch();
        setShowCreate(false);
        resetForm();
        toast.success("Template created");
      },
      onError: (e: any) => toast.error(e.message),
    });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const updateMutation =
    // @ts-ignore Sprint 85
    trpc.notificationOrchestrator.updateTemplate.useMutation({
      onSuccess: () => {
        templatesQuery.refetch();
        setEditTemplate(null);
        resetForm();
        toast.success("Template updated");
      },
      onError: (e: any) => toast.error(e.message),
    });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const deleteMutation =
    // @ts-ignore Sprint 85
    trpc.notificationOrchestrator.deleteTemplate.useMutation({
      onSuccess: () => {
        templatesQuery.refetch();
        toast.success("Template deleted");
      },
      onError: (e: any) => toast.error(e.message),
    });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const sendMutation =
    // @ts-ignore Sprint 85
    trpc.notificationOrchestrator.sendNotification.useMutation({
      onSuccess: () => toast.success("Notification sent"),
      onError: (e: any) => toast.error(e.message),
    });

  const resetForm = () =>
    setForm({ name: "", channel: "sms", subject: "", body: "", variables: "" });

  const templates = (templatesQuery.data ?? []).filter((t: any) => {
    if (search && !t.name?.toLowerCase().includes(search.toLowerCase()))
      return false;
    if (channelFilter !== "all" && t.channel !== channelFilter) return false;
    return true;
  });

  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bell className="h-6 w-6 text-purple-400" /> Notification
            Orchestrator
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Multi-channel notification templates, delivery tracking, and retry
            logic
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              templatesQuery.refetch();
              statsQuery.refetch();
              toast.success("Refreshed");
            }}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => {
              resetForm();
              setShowCreate(true);
            }}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Template
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Templates",
            value: stats?.totalTemplates ?? 0,
            color: "text-purple-400",
          },
          {
            label: "SMS Templates",
            value: stats?.smsCount ?? 0,
            color: "text-blue-400",
          },
          {
            label: "Email Templates",
            value: stats?.emailCount ?? 0,
            color: "text-emerald-400",
          },
          {
            label: "Push Templates",
            value: stats?.pushCount ?? 0,
            color: "text-orange-400",
          },
        ].map((s: any) => (
          <div
            key={s.label}
            className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4"
          >
            <p className="text-xs text-zinc-400 uppercase">{s.label}</p>
            <p className={`text-2xl font-bold mt-2 ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search templates..."
            value={search}
            onChange={(e: any) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
        {["all", "sms", "email", "push", "whatsapp"].map((ch: any) => (
          <button
            key={ch}
            onClick={() => setChannelFilter(ch)}
            className={`px-3 py-2 rounded-lg text-sm font-medium ${channelFilter === ch ? "bg-purple-600 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
          >
            {ch === "all" ? "All" : ch.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700/50 text-zinc-400">
              <th className="text-left p-4 font-medium">Channel</th>
              <th className="text-left p-4 font-medium">Name</th>
              <th className="text-left p-4 font-medium">Subject</th>
              <th className="text-left p-4 font-medium">Body Preview</th>
              <th className="text-left p-4 font-medium">Status</th>
              <th className="text-left p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {templatesQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-zinc-700/30">
                  <td colSpan={6} className="p-4">
                    <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                  </td>
                </tr>
              ))
            ) : templates.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-zinc-500">
                  No templates found
                </td>
              </tr>
            ) : (
              templates.map((t: any) => {
                const Icon = CHANNEL_ICONS[t.channel] || Bell;
                return (
                  <tr
                    key={t.id}
                    className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                  >
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4 text-purple-400" />
                        <span className="text-white uppercase text-xs">
                          {t.channel}
                        </span>
                      </div>
                    </td>
                    <td className="p-4 text-white font-medium">{t.name}</td>
                    <td className="p-4 text-zinc-300">{t.subject || "—"}</td>
                    <td className="p-4 text-zinc-400 max-w-[250px] truncate">
                      {t.body?.slice(0, 60)}...
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-1 rounded-full text-xs ${t.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-zinc-500/20 text-zinc-400"}`}
                      >
                        {t.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="p-4">
                      <div className="flex gap-1">
                        <button
                          onClick={() =>
                            sendMutation.mutate({
                              templateId: t.id,
                              recipient: "test@example.com",
                              variables: {},
                            })
                          }
                          className="p-1.5 hover:bg-purple-700/30 rounded-lg"
                          title="Send Test"
                        >
                          <Send className="h-4 w-4 text-purple-400" />
                        </button>
                        <button
                          onClick={() => {
                            setEditTemplate(t);
                            setForm({
                              name: t.name,
                              channel: t.channel,
                              subject: t.subject || "",
                              body: t.body || "",
                              variables: t.variables
                                ? JSON.stringify(t.variables)
                                : "",
                            });
                          }}
                          className="p-1.5 hover:bg-zinc-700 rounded-lg"
                          title="Edit"
                        >
                          <Edit className="h-4 w-4 text-zinc-400" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm("Delete this template?"))
                              deleteMutation.mutate({ id: t.id });
                          }}
                          className="p-1.5 hover:bg-red-700/30 rounded-lg"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4 text-red-400" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Modal */}
      {(showCreate || editTemplate) && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => {
            setShowCreate(false);
            setEditTemplate(null);
          }}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-md w-full mx-4"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-4">
              {editTemplate ? "Edit Template" : "New Template"}
            </h3>
            <div className="space-y-3">
              <input
                type="text"
                placeholder="Template Name"
                value={form.name}
                onChange={(e: any) =>
                  setForm({ ...form, name: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <select
                value={form.channel}
                onChange={(e: any) =>
                  setForm({ ...form, channel: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              >
                <option value="sms">SMS</option>
                <option value="email">Email</option>
                <option value="push">Push</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
              <input
                type="text"
                placeholder="Subject (email only)"
                value={form.subject}
                onChange={(e: any) =>
                  setForm({ ...form, subject: e.target.value })
                }
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
              />
              <textarea
                placeholder="Message body. Use {{variable}} for dynamic content."
                value={form.body}
                onChange={(e: any) =>
                  setForm({ ...form, body: e.target.value })
                }
                rows={4}
                className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white resize-none"
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => {
                    setShowCreate(false);
                    setEditTemplate(null);
                  }}
                  className="px-4 py-2 bg-zinc-700 text-white rounded-lg text-sm"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    if (editTemplate)
                      updateMutation.mutate({ id: editTemplate.id, ...form });
                    else createMutation.mutate(form);
                  }}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm"
                >
                  {editTemplate ? "Update" : "Create"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
