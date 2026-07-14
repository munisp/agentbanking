import {
    AlertCircle,
    Globe,
    Loader2,
    MessageSquare,
    MoreVertical,
    Paperclip,
    Phone,
    Search,
    Send,
    Smile,
    Store,
    Video,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { inventoryApi, messagingApi } from "../utils/api";

const Communication = () => {
  const [businesses, setBusinesses] = useState([]);
  const [businessesLoading, setBusinessesLoading] = useState(true);
  const [selectedStoreId, setSelectedStoreId] = useState("");

  const [conversations, setConversations] = useState([]);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [messageInput, setMessageInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [supportedLanguages, setSupportedLanguages] = useState({});
  const [showLanguageModal, setShowLanguageModal] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState("en");
  const [autoTranslate, setAutoTranslate] = useState(true);
  const [translations, setTranslations] = useState({});
  const [translatingIds, setTranslatingIds] = useState(new Set());

  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  // Load agent's stores/businesses on mount
  useEffect(() => {
    const loadBusinesses = async () => {
      setBusinessesLoading(true);
      try {
        const keycloakId = localStorage.getItem("keycloakId");
        if (!keycloakId) return;
        const data = await inventoryApi.getStores(keycloakId);
        const list = Array.isArray(data) ? data : (data?.stores ?? []);
        setBusinesses(list);
        // Auto-select first store if only one
        if (list.length === 1) {
          setSelectedStoreId(String(list[0].id));
        }
      } catch (err) {
        console.error("Error loading stores:", err);
      } finally {
        setBusinessesLoading(false);
      }
    };

    const loadLanguages = async () => {
      try {
        const data = await messagingApi.getSupportedLanguages();
        setSupportedLanguages(data.languages || {});
      } catch (err) {
        console.error("Error loading languages:", err);
      }
    };

    loadBusinesses();
    loadLanguages();

    // WebSocket for real-time notifications
    try {
      wsRef.current = messagingApi.connectWebSocket((data) => {
        if (data.type === "new_message") {
          if (selectedStoreId) {
            loadConversationsForStore(selectedStoreId);
          }
          if (data.conversation_id === selectedConversationId) {
            loadMessages(data.conversation_id);
          }
        }
      });
    } catch (err) {
      console.error("WebSocket connection failed:", err);
    }

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // When selected store changes, load its conversations
  useEffect(() => {
    if (!selectedStoreId) {
      setConversations([]);
      setSelectedConversationId(null);
      setMessages([]);
      return;
    }
    loadConversationsForStore(selectedStoreId);
    setSelectedConversationId(null);
    setMessages([]);
  }, [selectedStoreId]);

  // When selected conversation changes, load messages
  useEffect(() => {
    if (!selectedConversationId) return;
    loadMessages(selectedConversationId);
    markAsRead(selectedConversationId);
    const conv = conversations.find((c) => c.id === selectedConversationId);
    if (conv) {
      setSelectedLanguage(conv.agent_language || "en");
      setAutoTranslate(conv.auto_translate !== false);
    }
  }, [selectedConversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadConversationsForStore = async (storeEntityId) => {
    setLoading(true);
    setError(null);
    try {
      // Conversations for this store use the store's business_id as the agent keycloak_id
      // because the customer portal creates conversations with store.entity_id as agent_keycloak_id
      const data = await messagingApi.getConversations(storeEntityId);
      setConversations(data);
      if (data.length > 0) {
        setSelectedConversationId(data[0].id);
      }
    } catch (err) {
      console.error("Error loading conversations:", err);
      setError("Failed to load conversations for this store");
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (conversationId) => {
    try {
      const data = await messagingApi.getMessages(conversationId);
      setMessages(data);
      if (autoTranslate && selectedLanguage && selectedLanguage !== "en") {
        autoTranslateMessages(data, selectedLanguage);
      }
    } catch (err) {
      console.error("Error loading messages:", err);
    }
  };

  const markAsRead = async (conversationId) => {
    try {
      // Pass storeEntityId so the service verifies correctly (conversations belong to the store)
      await messagingApi.markAsRead(conversationId, selectedStoreId || null);
      setConversations((prev) =>
        prev.map((conv) =>
          conv.id === conversationId ? { ...conv, unread_count: 0 } : conv,
        ),
      );
    } catch (err) {
      console.error("Error marking as read:", err);
    }
  };

  const translateSingle = async (messageId, text, targetLang) => {
    if (!text || !targetLang || targetLang === "en" || translations[messageId])
      return;
    setTranslatingIds((prev) => new Set(prev).add(messageId));
    try {
      const result = await messagingApi.translateText(text, targetLang);
      setTranslations((prev) => ({
        ...prev,
        [messageId]: result.translated_text,
      }));
    } catch (err) {
      console.error("Translation failed:", err);
    } finally {
      setTranslatingIds((prev) => {
        const s = new Set(prev);
        s.delete(messageId);
        return s;
      });
    }
  };

  const autoTranslateMessages = (msgs, targetLang) => {
    if (!targetLang || targetLang === "en") return;
    msgs
      .filter((m) => m.sender_type !== "agent" && !translations[m.id])
      .forEach((m) => translateSingle(m.id, m.content, targetLang));
  };

  const handleSendMessage = async () => {
    if (!messageInput.trim() || !selectedConversationId || sendingMessage)
      return;
    setSendingMessage(true);
    try {
      await messagingApi.sendMessage({
        conversation_id: selectedConversationId,
        content: messageInput.trim(),
        message_type: "text",
      });
      setMessageInput("");
      await loadMessages(selectedConversationId);
      await loadConversationsForStore(selectedStoreId);
    } catch (err) {
      console.error("Error sending message:", err);
      setError("Failed to send message");
    } finally {
      setSendingMessage(false);
    }
  };

  const handleLanguageUpdate = async () => {
    if (!selectedConversationId) return;
    try {
      await messagingApi.updateLanguagePreference(
        selectedConversationId,
        selectedLanguage,
        autoTranslate,
      );
      setShowLanguageModal(false);
      if (autoTranslate && selectedLanguage && selectedLanguage !== "en") {
        setTranslations({});
        autoTranslateMessages(messages, selectedLanguage);
      }
    } catch (err) {
      console.error("Error updating language:", err);
      setError("Failed to update language preference");
    }
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = diffMs / (1000 * 60 * 60);
    if (diffHours < 1) {
      const mins = Math.floor(diffMs / (1000 * 60));
      return mins < 1 ? "Just now" : `${mins} min ago`;
    } else if (diffHours < 24) {
      return date.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
        hour12: true,
      });
    } else if (diffHours < 48) {
      return "Yesterday";
    }
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  const getInitials = (name) =>
    name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);

  const selectedConversation = conversations.find(
    (c) => c.id === selectedConversationId,
  );
  const selectedBusiness = businesses.find(
    (b) => String(b.id) === selectedStoreId,
  );

  const filteredConversations = conversations.filter((conv) =>
    conv.customer_name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Messages</h1>
        <p className="text-gray-600 mt-1">
          View and respond to customer messages for your stores
        </p>
      </div>

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertCircle className="w-5 h-5 shrink-0" />
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-auto text-red-500 hover:text-red-700 text-xl leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Store Selector */}
      <div className="mb-4 bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-4">
        <Store className="h-5 w-5 text-gray-500 shrink-0" />
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select Store
          </label>
          {businessesLoading ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading stores...
            </div>
          ) : businesses.length === 0 ? (
            <p className="text-sm text-gray-500">
              No stores found. Register a business first.
            </p>
          ) : (
            <select
              value={selectedStoreId}
              onChange={(e) => setSelectedStoreId(e.target.value)}
              className="w-full max-w-sm px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">— Select a store —</option>
              {businesses.map((b) => (
                <option key={b.id} value={String(b.id)}>
                  {b.name || b.id}
                </option>
              ))}
            </select>
          )}
        </div>
        {selectedBusiness && (
          <span className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded-full text-xs font-medium">
            <Store className="h-3 w-3" />
            {selectedBusiness.name}
          </span>
        )}
      </div>

      {/* Chat UI */}
      {!selectedStoreId ? (
        <div
          className="bg-white rounded-lg border border-gray-200 flex items-center justify-center"
          style={{ height: "calc(100vh - 320px)" }}
        >
          <div className="text-center text-gray-400 space-y-3">
            <MessageSquare className="w-16 h-16 mx-auto opacity-30" />
            <p className="text-lg font-medium text-gray-500">
              Select a store to view messages
            </p>
            <p className="text-sm">Customer messages are grouped by store</p>
          </div>
        </div>
      ) : (
        <div
          className="bg-white rounded-lg shadow-md overflow-hidden"
          style={{ height: "calc(100vh - 320px)" }}
        >
          <div className="flex h-full">
            {/* Conversations List */}
            <div className="w-1/3 border-r border-gray-200 flex flex-col">
              <div className="p-4 border-b border-gray-200">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search customers..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto">
                {loading ? (
                  <div className="flex items-center justify-center h-32 text-gray-400">
                    <Loader2 className="w-6 h-6 animate-spin mr-2" />
                    Loading...
                  </div>
                ) : filteredConversations.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <MessageSquare className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p className="font-medium">No conversations yet</p>
                    <p className="text-sm mt-1 text-gray-400">
                      Customers can message this store from the customer app
                    </p>
                  </div>
                ) : (
                  filteredConversations.map((conv) => (
                    <div
                      key={conv.id}
                      onClick={() => setSelectedConversationId(conv.id)}
                      className={`p-4 border-b border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors ${
                        selectedConversationId === conv.id
                          ? "bg-blue-50 border-l-4 border-l-blue-500"
                          : ""
                      }`}
                    >
                      <div className="flex items-start space-x-3">
                        <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold text-sm shrink-0">
                          {getInitials(conv.customer_name)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <p className="font-semibold text-gray-900 truncate text-sm">
                              {conv.customer_name}
                            </p>
                            <span className="text-xs text-gray-400 shrink-0 ml-1">
                              {conv.last_message_at
                                ? formatTimestamp(conv.last_message_at)
                                : ""}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500 truncate mt-0.5">
                            {conv.last_message || "No messages yet"}
                          </p>
                        </div>
                        {conv.unread_count > 0 && (
                          <div className="w-5 h-5 bg-blue-600 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0">
                            {conv.unread_count}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Chat Area */}
            <div className="flex-1 flex flex-col">
              {selectedConversation ? (
                <>
                  {/* Chat Header */}
                  <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-white">
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-semibold">
                        {getInitials(selectedConversation.customer_name)}
                      </div>
                      <div>
                        <p className="font-semibold text-gray-900">
                          {selectedConversation.customer_name}
                        </p>
                        <p className="text-xs text-gray-500">
                          Messaging via{" "}
                          <span className="font-medium text-blue-600">
                            {selectedBusiness?.name}
                          </span>
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => setShowLanguageModal(true)}
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                        title="Language Settings"
                      >
                        <Globe className="h-5 w-5 text-gray-600" />
                      </button>
                      {/* <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                        <Phone className="h-5 w-5 text-gray-600" />
                      </button>
                      <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                        <Video className="h-5 w-5 text-gray-600" />
                      </button>
                      <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                        <MoreVertical className="h-5 w-5 text-gray-600" />
                      </button> */}
                    </div>
                  </div>

                  {/* Messages */}
                  <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                    {messages.length === 0 ? (
                      <div className="flex items-center justify-center h-full text-gray-400">
                        No messages yet
                      </div>
                    ) : (
                      messages.map((message) => (
                        <div
                          key={message.id}
                          className={`flex ${message.sender_type === "agent" ? "justify-end" : "justify-start"}`}
                        >
                          <div className="max-w-xs lg:max-w-md xl:max-w-lg">
                            <div
                              className={`rounded-lg px-4 py-2 ${
                                message.sender_type === "agent"
                                  ? "bg-blue-600 text-white"
                                  : "bg-white text-gray-900 border border-gray-200"
                              }`}
                            >
                              {message.sender_type !== "agent" ? (
                                translations[message.id] ? (
                                  <>
                                    <p className="text-sm">
                                      {translations[message.id]}
                                    </p>
                                    <details className="mt-1">
                                      <summary className="text-xs opacity-60 cursor-pointer select-none">
                                        Original
                                      </summary>
                                      <p className="text-xs mt-1 opacity-60 italic">
                                        {message.content}
                                      </p>
                                    </details>
                                  </>
                                ) : (
                                  <>
                                    <p className="text-sm">{message.content}</p>
                                    {selectedLanguage &&
                                      selectedLanguage !== "en" && (
                                        <button
                                          onClick={() =>
                                            translateSingle(
                                              message.id,
                                              message.content,
                                              selectedLanguage,
                                            )
                                          }
                                          disabled={translatingIds.has(
                                            message.id,
                                          )}
                                          className="mt-1 text-xs text-blue-500 hover:underline disabled:opacity-50"
                                        >
                                          {translatingIds.has(message.id)
                                            ? "Translating..."
                                            : "Translate"}
                                        </button>
                                      )}
                                  </>
                                )
                              ) : (
                                <p className="text-sm">{message.content}</p>
                              )}
                            </div>
                            <p
                              className={`text-xs text-gray-400 mt-1 ${
                                message.sender_type === "agent"
                                  ? "text-right"
                                  : "text-left"
                              }`}
                            >
                              {formatTimestamp(message.created_at)}
                              {message.is_read &&
                                message.sender_type === "agent" && (
                                  <span className="ml-1">✓✓</span>
                                )}
                              {message.translation_engine &&
                                message.translation_engine !==
                                  "passthrough" && (
                                  <span
                                    className="ml-1"
                                    title={`Translated by ${message.translation_engine}`}
                                  >
                                    🌐
                                  </span>
                                )}
                            </p>
                          </div>
                        </div>
                      ))
                    )}
                    <div ref={messagesEndRef} />
                  </div>

                  {/* Message Input */}
                  <div className="p-4 border-t border-gray-200 bg-white">
                    <div className="flex flex-nowrap items-end gap-2 w-full">
                      <button
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0 min-w-[40px]"
                        type="button"
                      >
                        <Paperclip className="h-5 w-5 text-gray-600" />
                      </button>
                      <div className="flex-1 min-w-0">
                        <textarea
                          value={messageInput}
                          onChange={(e) => {
                            setMessageInput(e.target.value);
                            // Auto-expand height
                            e.target.style.height = "auto";
                            e.target.style.height =
                              Math.min(e.target.scrollHeight, 120) + "px";
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                              e.preventDefault();
                              handleSendMessage();
                            }
                          }}
                          placeholder={`Reply as ${selectedBusiness?.name || "agent"}...`}
                          rows={1}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none bg-white text-sm md:text-base min-h-[44px] max-h-[120px] overflow-y-auto"
                          disabled={sendingMessage}
                          style={{
                            minHeight: 44,
                            maxHeight: 120,
                            lineHeight: 1.5,
                          }}
                        />
                      </div>
                      <button
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0 min-w-[40px]"
                        type="button"
                      >
                        <Smile className="h-5 w-5 text-gray-600" />
                      </button>
                      <button
                        onClick={handleSendMessage}
                        disabled={sendingMessage || !messageInput.trim()}
                        className="p-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0 flex items-center justify-center min-w-[44px] min-h-[44px]"
                        type="button"
                      >
                        {sendingMessage ? (
                          <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                          <Send className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex items-center justify-center bg-gray-50">
                  <div className="text-center text-gray-400 space-y-2">
                    <MessageSquare className="w-12 h-12 mx-auto opacity-30" />
                    <p>Select a conversation to start messaging</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Language Settings Modal */}
      {showLanguageModal && selectedConversation && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowLanguageModal(false)}
        >
          <div
            className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-xl font-bold text-gray-900">
                  Language Settings
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Choose your preferred language for messaging
                </p>
              </div>
              <button
                onClick={() => setShowLanguageModal(false)}
                className="text-gray-400 hover:text-gray-600 text-2xl"
              >
                ×
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Your Language
                </label>
                <select
                  value={selectedLanguage}
                  onChange={(e) => setSelectedLanguage(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {Object.entries(supportedLanguages).map(([code, lang]) => (
                    <option key={code} value={code}>
                      {lang.native} ({lang.name})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Customer's Language
                </label>
                <div className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700">
                  {supportedLanguages[selectedConversation.customer_language]
                    ?.native || selectedConversation.customer_language}{" "}
                  (
                  {supportedLanguages[selectedConversation.customer_language]
                    ?.name || selectedConversation.customer_language}
                  )
                </div>
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="autoTranslate"
                  checked={autoTranslate}
                  onChange={(e) => setAutoTranslate(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label
                  htmlFor="autoTranslate"
                  className="ml-2 block text-sm text-gray-700"
                >
                  Enable automatic translation
                </label>
              </div>

              {selectedLanguage !== selectedConversation.customer_language && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm text-blue-700">
                    <strong>Translation enabled:</strong> Your messages in{" "}
                    {supportedLanguages[selectedLanguage]?.name} will be
                    automatically translated to{" "}
                    {
                      supportedLanguages[selectedConversation.customer_language]
                        ?.name
                    }
                  </p>
                </div>
              )}
            </div>

            <div className="flex gap-3 pt-4 border-t border-gray-200">
              <button
                onClick={() => setShowLanguageModal(false)}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleLanguageUpdate}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Communication;
