import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../config/role_nav_config.dart';

/// Navigation group definition
class NavGroup {
  final String id;
  final String label;
  final IconData icon;
  final List<NavItem> items;

  const NavGroup({
    required this.id,
    required this.label,
    required this.icon,
    required this.items,
  });
}

class NavItem {
  final String path;
  final String label;
  final IconData icon;

  const NavItem({
    required this.path,
    required this.label,
    required this.icon,
  });
}

/// All navigation groups — mirrors the PWA DashboardLayout structure
const List<NavGroup> navGroups = [
  NavGroup(id: 'core', label: 'Core', icon: Icons.dashboard, items: [
    NavItem(path: '/dashboard', label: 'POS Terminal', icon: Icons.point_of_sale),
    NavItem(path: '/wallet', label: 'Wallet', icon: Icons.account_balance_wallet),
    NavItem(path: '/float', label: 'Float Balance', icon: Icons.savings),
  ]),
  NavGroup(id: 'transactions', label: 'Transactions', icon: Icons.swap_horiz, items: [
    NavItem(path: '/cash-in', label: 'Cash In', icon: Icons.arrow_downward),
    NavItem(path: '/cash-out', label: 'Cash Out', icon: Icons.arrow_upward),
    NavItem(path: '/send-money', label: 'Send Money', icon: Icons.send),
    NavItem(path: '/receive-money', label: 'Receive Money', icon: Icons.call_received),
    NavItem(path: '/bill-payment', label: 'Bill Payment', icon: Icons.receipt_long),
    NavItem(path: '/history', label: 'Transaction History', icon: Icons.history),
  ]),
  NavGroup(id: 'finance', label: 'Finance & Payments', icon: Icons.attach_money, items: [
    NavItem(path: '/virtual-card', label: 'Virtual Card', icon: Icons.credit_card),
    NavItem(path: '/savings-goals', label: 'Savings Goals', icon: Icons.savings),
    NavItem(path: '/recurring-payments', label: 'Recurring Payments', icon: Icons.repeat),
    NavItem(path: '/payment-methods', label: 'Payment Methods', icon: Icons.payment),
    NavItem(path: '/exchange-rates', label: 'Exchange Rates', icon: Icons.currency_exchange),
    NavItem(path: '/rate-calculator', label: 'Rate Calculator', icon: Icons.calculate),
    NavItem(path: '/cards', label: 'My Cards', icon: Icons.credit_card),
    NavItem(path: '/customer-wallet', label: 'Customer Wallet', icon: Icons.account_balance_wallet),
    NavItem(path: '/multi-currency', label: 'Multi-Currency', icon: Icons.language),
  ]),
  NavGroup(id: 'beneficiaries', label: 'Beneficiaries', icon: Icons.people, items: [
    NavItem(path: '/beneficiaries', label: 'Beneficiaries', icon: Icons.people),
    NavItem(path: '/add-beneficiary', label: 'Add Beneficiary', icon: Icons.person_add),
  ]),
  NavGroup(id: 'agents', label: 'Agent & Compliance', icon: Icons.badge, items: [
    NavItem(path: '/agent-performance', label: 'Agent Performance', icon: Icons.trending_up),
    NavItem(path: '/kyc', label: 'KYC Verification', icon: Icons.verified_user),
    NavItem(path: '/kyc-verification', label: 'KYC Documents', icon: Icons.document_scanner),
    NavItem(path: '/compliance-scheduling', label: 'Compliance Schedule', icon: Icons.schedule),
    NavItem(path: '/audit-export', label: 'Audit Export', icon: Icons.download),
  ]),
  NavGroup(id: 'engagement', label: 'Engagement', icon: Icons.star, items: [
    NavItem(path: '/referral', label: 'Referral Program', icon: Icons.card_giftcard),
    NavItem(path: '/notifications', label: 'Notifications', icon: Icons.notifications),
    NavItem(path: '/notification-preferences', label: 'Notification Prefs', icon: Icons.tune),
  ]),
  NavGroup(id: 'account', label: 'Account & Security', icon: Icons.person, items: [
    NavItem(path: '/profile', label: 'Profile', icon: Icons.person),
    NavItem(path: '/settings', label: 'Settings', icon: Icons.settings),
    NavItem(path: '/security-settings', label: 'Security', icon: Icons.security),
    NavItem(path: '/biometric', label: 'Biometric Auth', icon: Icons.fingerprint),
  ]),
  NavGroup(id: 'tools', label: 'Tools', icon: Icons.build, items: [
    NavItem(path: '/qr-scanner', label: 'QR Scanner', icon: Icons.qr_code_scanner),
    NavItem(path: '/journeys', label: 'Journeys', icon: Icons.route),
  ]),
  NavGroup(id: 'future', label: 'Future Features', icon: Icons.rocket_launch, items: [
    NavItem(path: '/open-banking', label: 'Open Banking', icon: Icons.account_balance),
    NavItem(path: '/bnpl', label: 'BNPL Engine', icon: Icons.shopping_bag),
    NavItem(path: '/nfc-tap-to-pay', label: 'NFC Tap-to-Pay', icon: Icons.contactless),
    NavItem(path: '/ai-credit-scoring', label: 'AI Credit Scoring', icon: Icons.psychology),
    NavItem(path: '/agritech', label: 'AgriTech', icon: Icons.agriculture),
    NavItem(path: '/chat-banking', label: 'Chat Banking', icon: Icons.chat),
    NavItem(path: '/stablecoin', label: 'Stablecoin Rails', icon: Icons.currency_bitcoin),
    NavItem(path: '/wearable-payments', label: 'Wearable Payments', icon: Icons.watch),
    NavItem(path: '/satellite', label: 'Satellite Connect', icon: Icons.satellite_alt),
    NavItem(path: '/digital-identity', label: 'Digital Identity', icon: Icons.fingerprint),
  ]),
  NavGroup(id: 'help', label: 'Help & Support', icon: Icons.help_outline, items: [
    NavItem(path: '/help', label: 'Help Center', icon: Icons.help),
    NavItem(path: '/support', label: 'Support', icon: Icons.support_agent),
  ]),
];

/// 54Link App Drawer — full navigation system with collapsible groups,
/// search, role-based filtering, and active state tracking.
class AppDrawer extends ConsumerStatefulWidget {
  const AppDrawer({super.key});

  @override
  ConsumerState<AppDrawer> createState() => _AppDrawerState();
}

class _AppDrawerState extends ConsumerState<AppDrawer> {
  String _searchQuery = '';
  final Set<String> _collapsedGroups = {};
  final TextEditingController _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final user = auth.user;
    final role = parseRole(user?['role'] as String?);
    final currentPath = GoRouterState.of(context).uri.path;
    final theme = Theme.of(context);

    // Filter groups by role and search
    final visibleGroups = navGroups.where((g) => canAccessGroup(role, g.id)).toList();
    final filteredGroups = _searchQuery.isEmpty
        ? visibleGroups
        : visibleGroups
            .map((g) => NavGroup(
                  id: g.id,
                  label: g.label,
                  icon: g.icon,
                  items: g.items
                      .where((i) =>
                          i.label.toLowerCase().contains(_searchQuery.toLowerCase()) ||
                          i.path.toLowerCase().contains(_searchQuery.toLowerCase()))
                      .toList(),
                ))
            .where((g) => g.items.isNotEmpty)
            .toList();

    return Drawer(
      child: Column(
        children: [
          // Header
          DrawerHeader(
            decoration: BoxDecoration(
              color: theme.colorScheme.primary,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                CircleAvatar(
                  backgroundColor: Colors.white,
                  child: Text(
                    (user?['name'] as String? ?? 'A').substring(0, 1).toUpperCase(),
                    style: TextStyle(
                      color: theme.colorScheme.primary,
                      fontWeight: FontWeight.bold,
                      fontSize: 20,
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  user?['name'] as String? ?? 'Agent',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                ),
                Text(
                  user?['email'] as String? ?? '',
                  style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 12),
                ),
                const SizedBox(height: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    role.name.replaceAll(RegExp(r'(?=[A-Z])'), ' ').trim(),
                    style: const TextStyle(color: Colors.white, fontSize: 10),
                  ),
                ),
              ],
            ),
          ),

          // Search bar
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search menu...',
                prefixIcon: const Icon(Icons.search, size: 20),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(vertical: 8),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: BorderSide.none,
                ),
                filled: true,
                fillColor: theme.colorScheme.surfaceContainerHighest.withOpacity(0.5),
              ),
              onChanged: (v) => setState(() => _searchQuery = v),
            ),
          ),

          // Nav groups
          Expanded(
            child: ListView(
              padding: EdgeInsets.zero,
              children: filteredGroups.map((group) {
                final isCollapsed = _collapsedGroups.contains(group.id) && _searchQuery.isEmpty;
                final hasActiveItem = group.items.any((i) => currentPath == i.path);

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Group header
                    InkWell(
                      onTap: () {
                        setState(() {
                          if (_collapsedGroups.contains(group.id)) {
                            _collapsedGroups.remove(group.id);
                          } else {
                            _collapsedGroups.add(group.id);
                          }
                        });
                      },
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                        child: Row(
                          children: [
                            Icon(
                              isCollapsed ? Icons.chevron_right : Icons.expand_more,
                              size: 16,
                              color: hasActiveItem
                                  ? theme.colorScheme.primary
                                  : theme.colorScheme.onSurface.withOpacity(0.4),
                            ),
                            const SizedBox(width: 4),
                            Icon(group.icon, size: 14,
                                color: hasActiveItem
                                    ? theme.colorScheme.primary
                                    : theme.colorScheme.onSurface.withOpacity(0.4)),
                            const SizedBox(width: 6),
                            Text(
                              group.label.toUpperCase(),
                              style: TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.2,
                                color: hasActiveItem
                                    ? theme.colorScheme.primary
                                    : theme.colorScheme.onSurface.withOpacity(0.4),
                              ),
                            ),
                            const Spacer(),
                            Text(
                              '${group.items.length}',
                              style: TextStyle(
                                fontSize: 9,
                                color: theme.colorScheme.onSurface.withOpacity(0.3),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    // Group items
                    if (!isCollapsed)
                      ...group.items.map((item) {
                        final isActive = currentPath == item.path;
                        return ListTile(
                          dense: true,
                          visualDensity: const VisualDensity(vertical: -3),
                          leading: Icon(
                            item.icon,
                            size: 18,
                            color: isActive ? theme.colorScheme.primary : null,
                          ),
                          title: Text(
                            item.label,
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: isActive ? FontWeight.w600 : FontWeight.normal,
                              color: isActive ? theme.colorScheme.primary : null,
                            ),
                          ),
                          selected: isActive,
                          selectedTileColor: theme.colorScheme.primary.withOpacity(0.08),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 24),
                          onTap: () {
                            Navigator.pop(context); // Close drawer
                            context.go(item.path);
                          },
                        );
                      }),
                  ],
                );
              }).toList(),
            ),
          ),

          // Footer — sign out
          const Divider(height: 1),
          ListTile(
            leading: const Icon(Icons.logout, color: Colors.red),
            title: const Text('Sign Out', style: TextStyle(color: Colors.red)),
            onTap: () {
              ref.read(authProvider.notifier).logout();
              context.go('/login');
            },
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}
