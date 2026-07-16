import {
    AlertTriangle,
    CheckCircle,
    ChevronDown,
    ChevronRight,
    Clock,
    Loader2,
    RefreshCw,
    X,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import {
    api,
    type MdmDevice,
    type MdmPendingCommand,
} from "../../utils/api";

/* ─────────────────────────── command catalogue ─────────────────────────── */

type ParamField = {
  key: string;
  label: string;
  type: "text" | "number" | "textarea";
  placeholder?: string;
};

type CommandDef = {
  type: string;
  label: string;
  description: string;
  destructive?: boolean;
  confirm?: string;
  params?: ParamField[];
};

const COMMAND_GROUPS: { label: string; color: string; commands: CommandDef[] }[] =
  [
    {
      label: "Device Control",
      color: "blue",
      commands: [
        {
          type: "reboot",
          label: "Reboot",
          description: "Gracefully restart the terminal OS.",
        },
        {
          type: "lock_terminal",
          label: "Lock Terminal",
          description: "Freeze the screen and disable input until unlocked.",
        },
        {
          type: "unlock_terminal",
          label: "Unlock Terminal",
          description: "Release a previously locked terminal.",
        },
        {
          type: "factory_reset",
          label: "Factory Reset",
          description: "Wipe device to factory defaults.",
          destructive: true,
          confirm:
            "This will erase ALL data and reset to factory settings. Continue?",
        },
        {
          type: "screenshot",
          label: "Screenshot",
          description: "Capture and upload the current screen.",
        },
      ],
    },
    {
      label: "Diagnostics",
      color: "purple",
      commands: [
        {
          type: "get_diagnostics",
          label: "Get Diagnostics",
          description: "Collect battery, memory, CPU and connectivity metrics.",
        },
        {
          type: "log_upload",
          label: "Upload Logs",
          description: "Push device logs to the cloud for analysis.",
        },
        {
          type: "clear_cache",
          label: "Clear Cache",
          description: "Flush app caches and temp files.",
        },
      ],
    },
    {
      label: "Security",
      color: "red",
      commands: [
        {
          type: "remote_wipe",
          label: "Remote Wipe",
          description: "Erase all user data from the device immediately.",
          destructive: true,
          confirm:
            "This will PERMANENTLY erase all terminal data. Are you sure?",
        },
        {
          type: "enable_tamper_protection",
          label: "Enable Tamper Protection",
          description: "Activate physical tamper sensors on the terminal.",
        },
        {
          type: "disable_tamper_protection",
          label: "Disable Tamper Protection",
          description:
            "Temporarily suspend tamper sensors (e.g. for maintenance).",
        },
        {
          type: "rotate_encryption_keys",
          label: "Rotate Encryption Keys",
          description: "Generate and deploy new transport encryption keys.",
        },
        {
          type: "push_key_injection",
          label: "Push Key Injection",
          description: "Inject new PCI keys into the HSM module.",
          params: [
            { key: "key_id", label: "Key ID", type: "text", placeholder: "e.g. dek-001" },
            {
              key: "key_data",
              label: "Encrypted Key Data (base64)",
              type: "textarea",
              placeholder: "Base64-encoded key blob",
            },
          ],
        },
      ],
    },
    {
      label: "Network",
      color: "teal",
      commands: [
        {
          type: "enable_offline_mode",
          label: "Enable Offline Mode",
          description: "Allow the terminal to operate without connectivity.",
        },
        {
          type: "disable_offline_mode",
          label: "Disable Offline Mode",
          description: "Require live connectivity for all transactions.",
        },
      ],
    },
    {
      label: "Geofence",
      color: "orange",
      commands: [
        {
          type: "enable_geofence",
          label: "Enable / Update Geofence",
          description:
            "Restrict terminal to a geographic area. Provide centre and radius.",
          params: [
            {
              key: "latitude",
              label: "Latitude",
              type: "number",
              placeholder: "e.g. 6.524379",
            },
            {
              key: "longitude",
              label: "Longitude",
              type: "number",
              placeholder: "e.g. 3.379206",
            },
            {
              key: "radius",
              label: "Radius (metres)",
              type: "number",
              placeholder: "e.g. 500",
            },
          ],
        },
        {
          type: "disable_geofence",
          label: "Disable Geofence",
          description: "Remove active geofence restriction from terminal.",
        },
      ],
    },
    {
      label: "APK / Firmware",
      color: "indigo",
      commands: [
        {
          type: "update_apk",
          label: "Update APK",
          description: "Push a new APK version to the terminal via URL.",
          params: [
            {
              key: "download_url",
              label: "APK Download URL",
              type: "text",
              placeholder: "https://cdn.example.com/app-v2.apk",
            },
            {
              key: "version",
              label: "Version Tag",
              type: "text",
              placeholder: "e.g. 2.4.1",
            },
          ],
        },
        {
          type: "update_firmware",
          label: "Update Firmware",
          description: "Flash new firmware to the terminal.",
          params: [
            {
              key: "firmware_url",
              label: "Firmware URL",
              type: "text",
              placeholder: "https://cdn.example.com/fw-v3.bin",
            },
            {
              key: "version",
              label: "Firmware Version",
              type: "text",
              placeholder: "e.g. 3.0.2",
            },
          ],
        },
      ],
    },
    {
      label: "Config",
      color: "gray",
      commands: [
        {
          type: "push_config",
          label: "Push Config",
          description: "Push JSON config overrides to the terminal.",
          params: [
            {
              key: "_json",
              label: "Config (JSON)",
              type: "textarea",
              placeholder: '{"max_offline_hours": 48, "receipt_copies": 2}',
            },
          ],
        },
      ],
    },
  ];

const COLOR_MAP: Record<string, string> = {
  blue: "bg-blue-50 border-blue-200 text-blue-700",
  purple: "bg-purple-50 border-purple-200 text-purple-700",
  red: "bg-red-50 border-red-200 text-red-700",
  teal: "bg-teal-50 border-teal-200 text-teal-700",
  orange: "bg-orange-50 border-orange-200 text-orange-700",
  indigo: "bg-indigo-50 border-indigo-200 text-indigo-700",
  gray: "bg-gray-50 border-gray-200 text-gray-700",
};

const BTN_COLOR_MAP: Record<string, string> = {
  blue: "bg-blue-600 hover:bg-blue-700",
  purple: "bg-purple-600 hover:bg-purple-700",
  red: "bg-red-600 hover:bg-red-700",
  teal: "bg-teal-600 hover:bg-teal-700",
  orange: "bg-orange-600 hover:bg-orange-700",
  indigo: "bg-indigo-600 hover:bg-indigo-700",
  gray: "bg-gray-600 hover:bg-gray-700",
};

/* ──────────────────────────────── component ─────────────────────────────── */

interface Props {
  device: MdmDevice;
  onClose: () => void;
}

const MDMCommandsDrawer: React.FC<Props> = ({ device, onClose }) => {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(
    new Set(["Device Control", "Geofence"]),
  );
  const [paramValues, setParamValues] = useState<Record<string, Record<string, string>>>(
    {},
  );
  const [sending, setSending] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<
    Record<string, { ok: boolean; msg: string }>
  >({});
  const [pendingCommands, setPendingCommands] = useState<MdmPendingCommand[]>(
    [],
  );
  const [loadingPending, setLoadingPending] = useState(false);
  const [activeTab, setActiveTab] = useState<"commands" | "pending">(
    "commands",
  );

  const loadPending = async () => {
    setLoadingPending(true);
    try {
      const res = await api.getMdmPendingCommands(device.terminal_id);
      setPendingCommands(res.commands ?? []);
    } catch {
      /* silent */
    } finally {
      setLoadingPending(false);
    }
  };

  useEffect(() => {
    void loadPending();
  }, [device.terminal_id]);

  const toggleGroup = (label: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const setParam = (cmdType: string, key: string, val: string) => {
    setParamValues((prev) => ({
      ...prev,
      [cmdType]: { ...(prev[cmdType] ?? {}), [key]: val },
    }));
  };

  const issueCommand = async (def: CommandDef) => {
    if (def.confirm && !window.confirm(def.confirm)) return;

    setSending((p) => ({ ...p, [def.type]: true }));
    setResults((p) => {
      const n = { ...p };
      delete n[def.type];
      return n;
    });

    try {
      let params: Record<string, unknown> | undefined;
      if (def.params) {
        const raw = paramValues[def.type] ?? {};
        if (def.params.some((f) => f.key === "_json")) {
          try {
            params = JSON.parse(raw["_json"] ?? "{}");
          } catch {
            throw new Error("Config JSON is invalid.");
          }
        } else {
          params = {};
          for (const field of def.params) {
            const v = raw[field.key] ?? "";
            if (!v) throw new Error(`"${field.label}" is required.`);
            params[field.key] =
              field.type === "number" ? parseFloat(v) : v;
          }
        }
      }

      await api.createMdmCommand({
        terminal_id: device.terminal_id,
        model_id: device.model_id,
        command_type: def.type,
        params,
        priority: def.destructive ? 10 : 5,
        issued_by:
          localStorage.getItem("keycloakId") ?? "admin-dashboard",
      });

      setResults((p) => ({
        ...p,
        [def.type]: { ok: true, msg: "Command queued successfully." },
      }));
      void loadPending();
    } catch (err) {
      setResults((p) => ({
        ...p,
        [def.type]: {
          ok: false,
          msg: err instanceof Error ? err.message : "Failed to queue command.",
        },
      }));
    } finally {
      setSending((p) => ({ ...p, [def.type]: false }));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ backgroundColor: "rgba(0,0,0,0.45)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-xl bg-white h-full flex flex-col shadow-2xl">
        {/* Header */}
        <div className="bg-primary text-white px-6 py-4 flex items-center justify-between shrink-0">
          <div>
            <p className="text-xs opacity-75 uppercase tracking-wider">
              MDM Remote Commands
            </p>
            <h2 className="text-lg font-bold">{device.terminal_id}</h2>
            <p className="text-sm opacity-80">
              {device.model_id} &middot; {device.state}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/20 transition"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b shrink-0">
          <button
            onClick={() => setActiveTab("commands")}
            className={`flex-1 py-3 text-sm font-semibold transition ${
              activeTab === "commands"
                ? "border-b-2 border-primary text-primary"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            All Commands
          </button>
          <button
            onClick={() => {
              setActiveTab("pending");
              void loadPending();
            }}
            className={`flex-1 py-3 text-sm font-semibold transition ${
              activeTab === "pending"
                ? "border-b-2 border-primary text-primary"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            Pending Queue{" "}
            {pendingCommands.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700 text-xs">
                {pendingCommands.length}
              </span>
            )}
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {activeTab === "commands" ? (
            <>
              {COMMAND_GROUPS.map((group) => (
                <div
                  key={group.label}
                  className="border border-gray-200 rounded-xl overflow-hidden"
                >
                  {/* Group header */}
                  <button
                    className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 hover:bg-gray-100 transition text-left"
                    onClick={() => toggleGroup(group.label)}
                  >
                    <span className="font-semibold text-gray-800 text-sm">
                      {group.label}
                    </span>
                    {expandedGroups.has(group.label) ? (
                      <ChevronDown size={16} className="text-gray-500" />
                    ) : (
                      <ChevronRight size={16} className="text-gray-500" />
                    )}
                  </button>

                  {expandedGroups.has(group.label) && (
                    <div className="divide-y divide-gray-100">
                      {group.commands.map((cmd) => (
                        <div key={cmd.type} className="p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1">
                              <p className="font-medium text-gray-900 text-sm">
                                {cmd.label}
                              </p>
                              <p className="text-xs text-gray-500 mt-0.5">
                                {cmd.description}
                              </p>
                            </div>
                            {!cmd.params && (
                              <button
                                onClick={() => issueCommand(cmd)}
                                disabled={
                                  sending[cmd.type] ||
                                  device.state === "decommissioned"
                                }
                                className={`shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold text-white transition disabled:opacity-50 ${
                                  cmd.destructive
                                    ? "bg-red-600 hover:bg-red-700"
                                    : BTN_COLOR_MAP[group.color]
                                }`}
                              >
                                {sending[cmd.type] ? (
                                  <Loader2 size={14} className="animate-spin" />
                                ) : (
                                  "Send"
                                )}
                              </button>
                            )}
                          </div>

                          {/* Param form */}
                          {cmd.params && (
                            <div className="mt-3 space-y-2">
                              {cmd.params.map((field) =>
                                field.type === "textarea" ? (
                                  <div key={field.key}>
                                    <label className="text-xs text-gray-600 font-medium">
                                      {field.label}
                                    </label>
                                    <textarea
                                      rows={3}
                                      placeholder={field.placeholder}
                                      value={
                                        paramValues[cmd.type]?.[field.key] ??
                                        ""
                                      }
                                      onChange={(e) =>
                                        setParam(
                                          cmd.type,
                                          field.key,
                                          e.target.value,
                                        )
                                      }
                                      className="w-full mt-1 border border-gray-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                                    />
                                  </div>
                                ) : (
                                  <div key={field.key}>
                                    <label className="text-xs text-gray-600 font-medium">
                                      {field.label}
                                    </label>
                                    <input
                                      type={field.type}
                                      placeholder={field.placeholder}
                                      value={
                                        paramValues[cmd.type]?.[field.key] ??
                                        ""
                                      }
                                      onChange={(e) =>
                                        setParam(
                                          cmd.type,
                                          field.key,
                                          e.target.value,
                                        )
                                      }
                                      className="w-full mt-1 border border-gray-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                                    />
                                  </div>
                                ),
                              )}
                              <button
                                onClick={() => issueCommand(cmd)}
                                disabled={
                                  sending[cmd.type] ||
                                  device.state === "decommissioned"
                                }
                                className={`w-full py-2 rounded-lg text-xs font-semibold text-white transition disabled:opacity-50 ${
                                  cmd.destructive
                                    ? "bg-red-600 hover:bg-red-700"
                                    : BTN_COLOR_MAP[group.color]
                                }`}
                              >
                                {sending[cmd.type] ? (
                                  <span className="flex items-center justify-center gap-2">
                                    <Loader2
                                      size={14}
                                      className="animate-spin"
                                    />
                                    Sending…
                                  </span>
                                ) : (
                                  `Send: ${cmd.label}`
                                )}
                              </button>
                            </div>
                          )}

                          {/* Result feedback */}
                          {results[cmd.type] && (
                            <div
                              className={`mt-2 flex items-center gap-2 text-xs px-3 py-2 rounded-lg ${
                                results[cmd.type].ok
                                  ? "bg-green-50 text-green-700"
                                  : "bg-red-50 text-red-700"
                              }`}
                            >
                              {results[cmd.type].ok ? (
                                <CheckCircle size={13} />
                              ) : (
                                <AlertTriangle size={13} />
                              )}
                              {results[cmd.type].msg}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </>
          ) : (
            /* ── Pending tab ── */
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-gray-700">
                  Queued Commands
                </p>
                <button
                  onClick={() => void loadPending()}
                  disabled={loadingPending}
                  className="p-1.5 rounded hover:bg-gray-100 transition"
                >
                  <RefreshCw
                    size={14}
                    className={loadingPending ? "animate-spin" : ""}
                  />
                </button>
              </div>

              {loadingPending ? (
                <div className="flex justify-center py-10">
                  <Loader2 size={24} className="animate-spin text-gray-400" />
                </div>
              ) : pendingCommands.length === 0 ? (
                <div className="text-center text-gray-400 py-16">
                  <Clock size={32} className="mx-auto mb-2 opacity-40" />
                  <p className="text-sm">No pending commands</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {pendingCommands.map((cmd) => (
                    <div
                      key={cmd.command_id}
                      className="border border-gray-200 rounded-xl p-4"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-semibold text-sm text-gray-900">
                            {cmd.command_type}
                          </p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            Issued by {cmd.issued_by}
                          </p>
                          {cmd.params &&
                            Object.keys(cmd.params).length > 0 && (
                              <pre className="mt-2 text-xs bg-gray-50 rounded p-2 overflow-x-auto text-gray-700">
                                {JSON.stringify(cmd.params, null, 2)}
                              </pre>
                            )}
                        </div>
                        <div className="text-right shrink-0 ml-2">
                          <span
                            className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                              cmd.status === "completed"
                                ? "bg-green-100 text-green-700"
                                : cmd.status === "failed"
                                  ? "bg-red-100 text-red-700"
                                  : "bg-yellow-100 text-yellow-700"
                            }`}
                          >
                            {cmd.status}
                          </span>
                          <p className="text-xs text-gray-400 mt-1">
                            {new Date(cmd.issued_at).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MDMCommandsDrawer;
