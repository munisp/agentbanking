import {
    BarChart3,
    Bell,
    Filter,
    Mail,
    MessageSquare,
    Phone,
    Search,
    Send,
    Users,
} from "lucide-react";
import React, { useState } from "react";

const CommunicationManagement = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFilter, setSelectedFilter] = useState("all");

  const stats = [
    {
      label: "Total Messages",
      value: "12,458",
      icon: MessageSquare,
      color: "blue",
    },
    {
      label: "Active Conversations",
      value: "342",
      icon: Users,
      color: "green",
    },
    {
      label: "Notifications Sent",
      value: "5,234",
      icon: Bell,
      color: "purple",
    },
    { label: "Response Rate", value: "94%", icon: BarChart3, color: "orange" },
  ];

  const messages = [
    {
      id: 1,
      from: "Customer - John Doe",
      to: "Agent AG42385",
      subject: "Order Inquiry",
      status: "active",
      lastMessage: "When will my order be delivered?",
      time: "2 mins ago",
      unread: 2,
    },
    {
      id: 2,
      from: "Agent AG12345",
      to: "Customer - Jane Smith",
      subject: "Payment Confirmation",
      status: "resolved",
      lastMessage: "Payment has been confirmed",
      time: "1 hour ago",
      unread: 0,
    },
    {
      id: 3,
      from: "Customer - Mike Johnson",
      to: "Support Team",
      subject: "Technical Issue",
      status: "active",
      lastMessage: "I cannot access my account",
      time: "3 hours ago",
      unread: 1,
    },
  ];

  const notifications = [
    {
      id: 1,
      type: "SMS",
      recipients: 1250,
      subject: "New Product Launch",
      status: "sent",
      date: "2026-02-22",
    },
    {
      id: 2,
      type: "Email",
      recipients: 3420,
      subject: "Monthly Statement",
      status: "scheduled",
      date: "2026-02-25",
    },
    {
      id: 3,
      type: "Push",
      recipients: 5600,
      subject: "Special Offer",
      status: "sent",
      date: "2026-02-21",
    },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Communication Management
          </h1>
          <p className="text-gray-600 mt-1">
            Monitor and manage all platform communications
          </p>
        </div>
        <button className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors">
          <Send className="h-5 w-5 mr-2" />
          Send Notification
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stats.map((stat, index) => {
          const IconComponent = stat.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">{stat.label}</p>
                  <p
                    className={`text-2xl font-bold mt-2 text-${stat.color}-600`}
                  >
                    {stat.value}
                  </p>
                </div>
                <div className={`p-3 bg-${stat.color}-100 rounded-lg`}>
                  <IconComponent className={`h-6 w-6 text-${stat.color}-600`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Messages */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Recent Messages
            </h2>
            <div className="flex items-center space-x-2">
              <Search className="h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
              />
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className="p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="font-medium text-gray-900">
                        {message.subject}
                      </p>
                      <p className="text-sm text-gray-500">
                        {message.from} → {message.to}
                      </p>
                    </div>
                    {message.unread > 0 && (
                      <span className="bg-[var(--tenant-primary-color,#002082)] text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
                        {message.unread}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mb-2">
                    {message.lastMessage}
                  </p>
                  <div className="flex items-center justify-between">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        message.status === "active"
                          ? "bg-green-100 text-green-800"
                          : "bg-gray-100 text-gray-800"
                      }`}
                    >
                      {message.status}
                    </span>
                    <span className="text-xs text-gray-500">
                      {message.time}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Notification Campaigns */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">
              Notification Campaigns
            </h2>
          </div>
          <div className="p-6">
            <div className="space-y-4">
              {notifications.map((notification) => (
                <div
                  key={notification.id}
                  className="p-4 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      {notification.type === "SMS" && (
                        <Phone className="h-4 w-4 text-[var(--tenant-primary-color,#002082)]" />
                      )}
                      {notification.type === "Email" && (
                        <Mail className="h-4 w-4 text-purple-600" />
                      )}
                      {notification.type === "Push" && (
                        <Bell className="h-4 w-4 text-green-600" />
                      )}
                      <span className="text-sm font-medium text-gray-700">
                        {notification.type}
                      </span>
                    </div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                        notification.status === "sent"
                          ? "bg-green-100 text-green-800"
                          : "bg-yellow-100 text-yellow-800"
                      }`}
                    >
                      {notification.status}
                    </span>
                  </div>
                  <p className="font-medium text-gray-900 mb-1">
                    {notification.subject}
                  </p>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">
                      {notification.recipients.toLocaleString()} recipients
                    </span>
                    <span className="text-gray-500">{notification.date}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Communication Channels */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Communication Channels Performance
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            {
              channel: "SMS",
              sent: 5234,
              delivered: 5120,
              failed: 114,
              rate: "97.8%",
            },
            {
              channel: "Email",
              sent: 12458,
              delivered: 11890,
              failed: 568,
              rate: "95.4%",
            },
            {
              channel: "whatsapp",
              sent: 1858,
              delivered: 1790,
              failed: 68,
              rate: "97.4%",
            },
            {
              channel: "telegram",
              sent: 458,
              delivered: 450,
              failed: 8,
              rate: "99.1%",
            },
            {
              channel: "Push",
              sent: 18900,
              delivered: 17200,
              failed: 1700,
              rate: "91.0%",
            },
          ].map((channel, index) => (
            <div key={index} className="p-4 border border-gray-200 rounded-lg">
              <h3 className="font-medium text-gray-900 mb-3">
                {channel.channel} Notifications
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Sent:</span>
                  <span className="font-medium">
                    {channel.sent.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Delivered:</span>
                  <span className="font-medium text-green-600">
                    {channel.delivered.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Failed:</span>
                  <span className="font-medium text-red-600">
                    {channel.failed.toLocaleString()}
                  </span>
                </div>
                <div className="flex justify-between pt-2 border-t border-gray-200">
                  <span className="text-gray-600">Delivery Rate:</span>
                  <span className="font-bold text-[var(--tenant-primary-color,#002082)]">
                    {channel.rate}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CommunicationManagement;
