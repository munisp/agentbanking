import {
    AlertCircle,
    MessageSquare,
    MoreVertical,
    Paperclip,
    Search,
    Send,
    Smile,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { messagingApi } from "../utils/api";

const Communication = () => {
  const location = useLocation();
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [messageInput, setMessageInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [error, setError] = useState(null);

  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const selectedConversationIdRef = useRef(null);

  // Keep ref in sync so the WS callback can read the current value
  useEffect(() => {
    selectedConversationIdRef.current = selectedConversationId;
  }, [selectedConversationId]);

  // ── Boot: load conversations + open WebSocket ──────────────────────
  useEffect(() => {
    loadConversations();

    try {
      const ws = messagingApi.connectWebSocket((data) => {
        if (data.type === "new_message") {
          const msg = data.message;
          if (msg.conversation_id === selectedConversationIdRef.current) {
            setMessages((prev) =>
              prev.find((m) => m.id === msg.id) ? prev : [...prev, msg],
            );
          }
          loadConversations(false);
        }
      });
      wsRef.current = ws;
    } catch {
      // WS unavailable — silent
    }

    return () => wsRef.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-open conversation from navigation state
  useEffect(() => {
    const targetId = location.state?.conversationId;
    if (targetId && conversations.length > 0 && !selectedConversationId) {
      const target = conversations.find((c) => c.id === targetId);
      if (target) selectConversation(target);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversations, location.state?.conversationId]);

  // ── API helpers ───────────────────────────────────────────────────
  const loadConversations = async (showLoading = true) => {
    if (showLoading) setLoadingConversations(true);
    try {
      const data = await messagingApi.getConversations();
      setConversations(
        Array.isArray(data) ? data : (data?.conversations ?? []),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingConversations(false);
    }
  };

  const selectConversation = async (conv) => {
    setSelectedConversationId(conv.id);
    setMessages([]);
    setLoadingMessages(true);
    try {
      const data = await messagingApi.getMessages(conv.id);
      setMessages(Array.isArray(data) ? data : (data?.messages ?? []));
      messagingApi.markAsRead(conv.id).catch(() => {});
      setConversations((prev) =>
        prev.map((c) => (c.id === conv.id ? { ...c, unread_count: 0 } : c)),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingMessages(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    const text = messageInput.trim();
    if (!text || !selectedConversationId || sendingMessage) return;

    setSendingMessage(true);
    setMessageInput("");
    try {
      const sent = await messagingApi.sendMessage(selectedConversationId, text);
      setMessages((prev) => [...prev, sent]);
      loadConversations(false);
    } catch (err) {
      setError(err.message);
      setMessageInput(text);
    } finally {
      setSendingMessage(false);
    }
  };

  // ── Display helpers ───────────────────────────────────────────────
  const formatTime = (ts) => {
    if (!ts) return "";
    const date = new Date(ts);
    const diffMin = Math.floor((Date.now() - date) / 60000);
    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    if (diffH < 48) return "Yesterday";
    return date.toLocaleDateString();
  };

  const formatMessageTime = (ts) =>
    ts
      ? new Date(ts).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : "";

  const getConvName = (conv) =>
    conv.agent_name ?? conv.customer_name ?? conv.name ?? "Agent";

  const getLastMessage = (conv) =>
    conv.last_message ?? conv.last_message_content ?? "";

  const getUnread = (conv) =>
    conv.unread_count ?? conv.customer_unread_count ?? 0;

  const isMyMessage = (msg) => msg.sender_type === "customer";

  const selectedConversation = conversations.find(
    (c) => c.id === selectedConversationId,
  );

  const filteredConversations = conversations.filter((conv) =>
    getConvName(conv).toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
        <p className="text-gray-600 mt-1">
          Chat with agents and customer support
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-auto font-medium hover:text-red-900"
          >
            Dismiss
          </button>
        </div>
      )}

      <div
        className="bg-white rounded-lg shadow overflow-hidden"
        style={{ height: "calc(100vh - 260px)" }}
      >
        <div className="flex h-full">
          {/* ── Conversations list ── */}
          <div className="w-full md:w-1/3 border-r border-gray-200 flex flex-col">
            <div className="p-4 border-b border-gray-200">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search conversations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingConversations ? (
                <div className="flex justify-center items-center h-full">
                  <span className="animate-pulse text-sm text-gray-400">
                    Loading conversations…
                  </span>
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-400 p-4 text-center">
                  <MessageSquare className="h-10 w-10 mb-2" />
                  <p className="text-sm">No conversations yet</p>
                </div>
              ) : (
                filteredConversations.map((conv) => {
                  const unread = getUnread(conv);
                  return (
                    <div
                      key={conv.id}
                      onClick={() => selectConversation(conv)}
                      className={`p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50 ${
                        selectedConversationId === conv.id ? "bg-green-50" : ""
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <div className="relative">
                          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center text-xl font-bold text-green-700">
                            {getConvName(conv).charAt(0).toUpperCase()}
                          </div>
                          {conv.is_online && (
                            <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 rounded-full border-2 border-white" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="font-medium text-gray-900 truncate">
                              {getConvName(conv)}
                            </p>
                            <span className="text-xs text-gray-500 shrink-0 ml-1">
                              {formatTime(
                                conv.last_message_at ?? conv.updated_at,
                              )}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 truncate">
                            {getLastMessage(conv)}
                          </p>
                        </div>
                        {unread > 0 && (
                          <span className="bg-green-600 text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center shrink-0">
                            {unread > 9 ? "9+" : unread}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* ── Chat area ── */}
          <div className="flex-1 flex flex-col">
            {selectedConversation ? (
              <>
                {/* Header */}
                <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center text-lg font-bold text-green-700">
                      {getConvName(selectedConversation)
                        .charAt(0)
                        .toUpperCase()}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">
                        {getConvName(selectedConversation)}
                      </p>
                      <p className="text-sm text-gray-500">
                        {selectedConversation.is_online ? "Online" : "Offline"}
                      </p>
                    </div>
                  </div>
                  <button className="p-2 hover:bg-gray-100 rounded-lg">
                    <MoreVertical className="h-5 w-5 text-gray-600" />
                  </button>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                  {loadingMessages ? (
                    <div className="flex justify-center items-center h-full">
                      <span className="animate-pulse text-sm text-gray-400">
                        Loading messages…
                      </span>
                    </div>
                  ) : messages.length === 0 ? (
                    <div className="flex justify-center items-center h-full text-gray-400 text-sm">
                      No messages yet — say hello!
                    </div>
                  ) : (
                    messages.map((message) => (
                      <div
                        key={message.id}
                        className={`flex ${isMyMessage(message) ? "justify-end" : "justify-start"}`}
                      >
                        <div
                          className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                            isMyMessage(message)
                              ? "bg-green-600 text-white"
                              : "bg-white text-gray-900 border border-gray-200"
                          }`}
                        >
                          <p className="text-sm">{message.content}</p>
                          <p
                            className={`text-xs mt-1 ${
                              isMyMessage(message)
                                ? "text-green-100"
                                : "text-gray-500"
                            }`}
                          >
                            {formatMessageTime(message.created_at)}
                          </p>
                        </div>
                      </div>
                    ))
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <form
                  onSubmit={handleSendMessage}
                  className="p-4 border-t border-gray-200"
                >
                  <div className="flex items-center space-x-2">
                    <button
                      type="button"
                      className="p-2 hover:bg-gray-100 rounded-lg"
                    >
                      <Paperclip className="h-5 w-5 text-gray-600" />
                    </button>
                    <input
                      type="text"
                      placeholder="Type a message…"
                      value={messageInput}
                      onChange={(e) => setMessageInput(e.target.value)}
                      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
                    />
                    <button
                      type="button"
                      className="p-2 hover:bg-gray-100 rounded-lg"
                    >
                      <Smile className="h-5 w-5 text-gray-600" />
                    </button>
                    <button
                      type="submit"
                      disabled={!messageInput.trim() || sendingMessage}
                      className="p-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Send className="h-5 w-5" />
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center bg-gray-50">
                <div className="text-center">
                  <MessageSquare className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">
                    Select a conversation to start messaging
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Communication;
