import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';


// ── Notification model ──────────────────────────────────────────────────────
enum NotificationType { transaction, alert, system, promotion, kyc }

class AppNotification {
  final String id;
  final NotificationType type;
  final String title;
  final String body;
  final DateTime timestamp;
  final bool isRead;
  final String? actionRoute;
  final Map<String, dynamic>? metadata;

  const AppNotification({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.timestamp,
    this.isRead = false,
    this.actionRoute,
    this.metadata,
  });

  AppNotification copyWith({bool? isRead}) => AppNotification(
        id: id,
        type: type,
        title: title,
        body: body,
        timestamp: timestamp,
        isRead: isRead ?? this.isRead,
        actionRoute: actionRoute,
        metadata: metadata,
      );
}

// ── Notifications provider ──────────────────────────────────────────────────
final notificationsProvider =
    StateNotifierProvider<NotificationsNotifier, List<AppNotification>>((ref) {
  return NotificationsNotifier();
});

class NotificationsNotifier extends StateNotifier<List<AppNotification>> {
  NotificationsNotifier() : super(_mockNotifications());

  void markRead(String id) {
    state = state
        .map((n) => n.id == id ? n.copyWith(isRead: true) : n)
        .toList();
  }

  void markAllRead() {
    state = state.map((n) => n.copyWith(isRead: true)).toList();
  }

  void delete(String id) {
    state = state.where((n) => n.id != id).toList();
  }

  void clearAll() {
    state = [];
  }

  int get unreadCount => state.where((n) => !n.isRead).length;

  static List<AppNotification> _mockNotifications() {
    final now = DateTime.now();
    return [
      AppNotification(
        id: 'n1',
        type: NotificationType.transaction,
        title: 'Cash-In Successful',
        body: 'NGN 50,000 deposited to account ending 4521. Reference: TXN-20240412-001',
        timestamp: now.subtract(const Duration(minutes: 5)),
        isRead: false,
        actionRoute: '/transaction-history',
      ),
      AppNotification(
        id: 'n2',
        type: NotificationType.alert,
        title: 'Low Float Balance',
        body: 'Your float balance is NGN 12,500 — below the recommended NGN 25,000 threshold.',
        timestamp: now.subtract(const Duration(hours: 1)),
        isRead: false,
        actionRoute: '/float',
      ),
      AppNotification(
        id: 'n3',
        type: NotificationType.kyc,
        title: 'KYC Verification Required',
        body: 'Customer John Doe (BVN: 2234****890) requires identity re-verification.',
        timestamp: now.subtract(const Duration(hours: 3)),
        isRead: true,
        actionRoute: '/kyc',
      ),
      AppNotification(
        id: 'n4',
        type: NotificationType.system,
        title: 'App Update Available',
        body: '54Link v2.5.1 is available. New features: rate lock, biometric login, and improved offline sync.',
        timestamp: now.subtract(const Duration(days: 1)),
        isRead: true,
      ),
      AppNotification(
        id: 'n5',
        type: NotificationType.promotion,
        title: '🎉 Bonus Commission This Week',
        body: 'Earn 1.5x commission on all international transfers until Sunday. T&Cs apply.',
        timestamp: now.subtract(const Duration(days: 2)),
        isRead: false,
        actionRoute: '/send-money',
      ),
      AppNotification(
        id: 'n6',
        type: NotificationType.transaction,
        title: 'Transfer Completed',
        body: 'NGN 25,000 sent to Fatima Abubakar (GTBank ****7890). Commission: NGN 125.',
        timestamp: now.subtract(const Duration(days: 3)),
        isRead: true,
        actionRoute: '/transaction-history',
      ),
    ];
  }
}

// ── Icon & colour helpers ───────────────────────────────────────────────────
IconData _iconFor(NotificationType t) {
  switch (t) {
    case NotificationType.transaction:
      return Icons.swap_horiz_rounded;
    case NotificationType.alert:
      return Icons.warning_amber_rounded;
    case NotificationType.system:
      return Icons.system_update_rounded;
    case NotificationType.promotion:
      return Icons.local_offer_rounded;
    case NotificationType.kyc:
      return Icons.verified_user_rounded;
  }
}

Color _colorFor(NotificationType t) {
  switch (t) {
    case NotificationType.transaction:
      return const Color(0xFF3B82F6);
    case NotificationType.alert:
      return const Color(0xFFF59E0B);
    case NotificationType.system:
      return const Color(0xFF6B7280);
    case NotificationType.promotion:
      return const Color(0xFF10B981);
    case NotificationType.kyc:
      return const Color(0xFF8B5CF6);
  }
}

String _labelFor(NotificationType t) {
  switch (t) {
    case NotificationType.transaction:
      return 'Transaction';
    case NotificationType.alert:
      return 'Alert';
    case NotificationType.system:
      return 'System';
    case NotificationType.promotion:
      return 'Promotion';
    case NotificationType.kyc:
      return 'KYC';
  }
}

// ── Main screen ─────────────────────────────────────────────────────────────
class NotificationScreen extends ConsumerStatefulWidget {
  const NotificationScreen({super.key});

  @override
  ConsumerState<NotificationScreen> createState() => _NotificationScreenState();
}

class _NotificationScreenState extends ConsumerState<NotificationScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  NotificationType? _filter;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final notifications = ref.watch(notificationsProvider);
    final notifier = ref.read(notificationsProvider.notifier);
    final unread = notifications.where((n) => !n.isRead).toList();
    final all = _filter == null
        ? notifications
        : notifications.where((n) => n.type == _filter).toList();

    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D1117),
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: Colors.white, size: 20),
          onPressed: () => context.pop(),
        ),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Notifications',
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600)),
            if (unread.isNotEmpty)
              Text('${unread.length} unread',
                  style: const TextStyle(color: Color(0xFF3B82F6), fontSize: 12)),
          ],
        ),
        actions: [
          if (unread.isNotEmpty)
            TextButton(
              onPressed: () => notifier.markAllRead(),
              child: const Text('Mark all read',
                  style: TextStyle(color: Color(0xFF3B82F6), fontSize: 13)),
            ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert, color: Colors.white70),
            color: const Color(0xFF1A2035),
            onSelected: (v) {
              if (v == 'clear') notifier.clearAll();
            },
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'clear',
                child: Text('Clear all', style: TextStyle(color: Colors.white70)),
              ),
            ],
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: const Color(0xFF3B82F6),
          labelColor: const Color(0xFF3B82F6),
          unselectedLabelColor: Colors.white54,
          tabs: [
            Tab(text: 'All (${notifications.length})'),
            Tab(text: 'Unread (${unread.length})'),
          ],
        ),
      ),
      body: Column(
        children: [
          // Filter chips
          _buildFilterChips(),
          // Tab content
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildList(all, notifier),
                _buildList(unread, notifier),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChips() {
    final types = NotificationType.values;
    return SizedBox(
      height: 48,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          _FilterChip(
            label: 'All',
            isSelected: _filter == null,
            color: const Color(0xFF3B82F6),
            onTap: () => setState(() => _filter = null),
          ),
          ...types.map((t) => Padding(
                padding: const EdgeInsets.only(left: 8),
                child: _FilterChip(
                  label: _labelFor(t),
                  isSelected: _filter == t,
                  color: _colorFor(t),
                  onTap: () => setState(() => _filter = _filter == t ? null : t),
                ),
              )),
        ],
      ),
    );
  }

  Widget _buildList(List<AppNotification> items, NotificationsNotifier notifier) {
    if (items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.notifications_none_rounded,
                size: 64, color: Colors.white.withOpacity(0.2)),
            const SizedBox(height: 16),
            Text('No notifications',
                style: TextStyle(color: Colors.white.withOpacity(0.4), fontSize: 16)),
          ],
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: items.length,
      separatorBuilder: (_, __) =>
          Divider(color: Colors.white.withOpacity(0.06), height: 1),
      itemBuilder: (ctx, i) => _NotificationTile(
        notification: items[i],
        onTap: () {
          notifier.markRead(items[i].id);
          if (items[i].actionRoute != null) {
            context.push(items[i].actionRoute!);
          }
        },
        onDismiss: () => notifier.delete(items[i].id),
      ),
    );
  }
}

// ── Notification tile ────────────────────────────────────────────────────────
class _NotificationTile extends StatelessWidget {
  final AppNotification notification;
  final VoidCallback onTap;
  final VoidCallback onDismiss;

  const _NotificationTile({
    required this.notification,
    required this.onTap,
    required this.onDismiss,
  });

  @override
  Widget build(BuildContext context) {
    final color = _colorFor(notification.type);
    final isUnread = !notification.isRead;
    final df = DateFormat('MMM d, h:mm a');

    return Dismissible(
      key: Key(notification.id),
      direction: DismissDirection.endToStart,
      onDismissed: (_) => onDismiss(),
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        color: const Color(0xFFEF4444),
        child: const Icon(Icons.delete_outline, color: Colors.white),
      ),
      child: InkWell(
        onTap: onTap,
        child: Container(
          color: isUnread
              ? color.withOpacity(0.05)
              : Colors.transparent,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Icon badge
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(_iconFor(notification.type), color: color, size: 20),
              ),
              const SizedBox(width: 12),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            notification.title,
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              fontWeight:
                                  isUnread ? FontWeight.w600 : FontWeight.w400,
                            ),
                          ),
                        ),
                        if (isUnread)
                          Container(
                            width: 8,
                            height: 8,
                            decoration: BoxDecoration(
                              color: color,
                              shape: BoxShape.circle,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      notification.body,
                      style: TextStyle(
                          color: Colors.white.withOpacity(0.6), fontSize: 13),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: color.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            _labelFor(notification.type),
                            style: TextStyle(
                                color: color,
                                fontSize: 10,
                                fontWeight: FontWeight.w600),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          df.format(notification.timestamp),
                          style: TextStyle(
                              color: Colors.white.withOpacity(0.4),
                              fontSize: 11),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Filter chip ──────────────────────────────────────────────────────────────
class _FilterChip extends StatelessWidget {
  final String label;
  final bool isSelected;
  final Color color;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    required this.isSelected,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? color.withOpacity(0.2) : const Color(0xFF1A2035),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? color : Colors.white.withOpacity(0.1),
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? color : Colors.white54,
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }
}
