import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
} from 'react-native';
import { DrawerContentScrollView } from '@react-navigation/drawer';
import { navGroups, NavGroup } from './navGroups';
import { canAccessGroup, parseRole, getRoleDisplayName, UserRole } from '../config/roleNavConfig';

interface CustomDrawerProps {
  navigation: any;
  state: any;
  userRole?: string;
  userName?: string;
  userEmail?: string;
}

const CustomDrawerContent: React.FC<CustomDrawerProps> = ({
  navigation,
  state,
  userRole,
  userName,
  userEmail,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const role = parseRole(userRole);
  const currentRouteName = state?.routes?.[state.index]?.name || '';

  const toggleGroup = (groupId: string) => {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  };

  // Filter by role and search
  const visibleGroups = navGroups.filter(g => canAccessGroup(role, g.id));
  const filteredGroups = searchQuery
    ? visibleGroups
        .map(g => ({
          ...g,
          items: g.items.filter(
            i =>
              i.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
              i.name.toLowerCase().includes(searchQuery.toLowerCase()),
          ),
        }))
        .filter(g => g.items.length > 0)
    : visibleGroups;

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {(userName || 'A').charAt(0).toUpperCase()}
          </Text>
        </View>
        <Text style={styles.userName}>{userName || 'Agent'}</Text>
        <Text style={styles.userEmail}>{userEmail || ''}</Text>
        <View style={styles.roleBadge}>
          <Text style={styles.roleText}>{getRoleDisplayName(role)}</Text>
        </View>
      </View>

      {/* Search */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search menu..."
          placeholderTextColor="#999"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {/* Nav Groups */}
      <ScrollView style={styles.navList}>
        {filteredGroups.map(group => {
          const isCollapsed = collapsedGroups.has(group.id) && !searchQuery;
          const hasActiveItem = group.items.some(i => i.name === currentRouteName);

          return (
            <View key={group.id}>
              {/* Group Header */}
              <TouchableOpacity
                style={styles.groupHeader}
                onPress={() => toggleGroup(group.id)}
              >
                <Text
                  style={[
                    styles.groupLabel,
                    hasActiveItem && styles.groupLabelActive,
                  ]}
                >
                  {isCollapsed ? '▸' : '▾'} {group.label.toUpperCase()}
                </Text>
                <Text style={styles.groupCount}>{group.items.length}</Text>
              </TouchableOpacity>

              {/* Group Items */}
              {!isCollapsed &&
                group.items.map(item => {
                  const isActive = item.name === currentRouteName;
                  return (
                    <TouchableOpacity
                      key={item.name}
                      style={[
                        styles.navItem,
                        isActive && styles.navItemActive,
                      ]}
                      onPress={() => {
                        navigation.navigate(item.name);
                      }}
                    >
                      <Text
                        style={[
                          styles.navItemLabel,
                          isActive && styles.navItemLabelActive,
                        ]}
                      >
                        {item.label}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
            </View>
          );
        })}
      </ScrollView>

      {/* Footer */}
      <TouchableOpacity style={styles.signOutBtn}>
        <Text style={styles.signOutText}>Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
};

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f172a' },
  header: {
    paddingTop: 50,
    paddingBottom: 16,
    paddingHorizontal: 16,
    backgroundColor: '#1e293b',
  },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#3b82f6',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  avatarText: { color: '#fff', fontSize: 20, fontWeight: 'bold' },
  userName: { color: '#f8fafc', fontSize: 16, fontWeight: 'bold' },
  userEmail: { color: '#94a3b8', fontSize: 12, marginTop: 2 },
  roleBadge: {
    backgroundColor: 'rgba(59,130,246,0.2)',
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignSelf: 'flex-start',
    marginTop: 6,
  },
  roleText: { color: '#93c5fd', fontSize: 10 },
  searchContainer: { paddingHorizontal: 12, paddingVertical: 8 },
  searchInput: {
    backgroundColor: '#1e293b',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    color: '#f8fafc',
    fontSize: 13,
  },
  navList: { flex: 1 },
  groupHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 4,
  },
  groupLabel: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.2,
    color: 'rgba(148,163,184,0.5)',
  },
  groupLabelActive: { color: '#3b82f6' },
  groupCount: { fontSize: 9, color: 'rgba(148,163,184,0.3)' },
  navItem: {
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 8,
    marginHorizontal: 8,
    marginVertical: 1,
  },
  navItemActive: { backgroundColor: 'rgba(59,130,246,0.1)' },
  navItemLabel: { fontSize: 13, color: '#cbd5e1' },
  navItemLabelActive: { color: '#3b82f6', fontWeight: '600' },
  signOutBtn: {
    borderTopWidth: 1,
    borderTopColor: '#1e293b',
    padding: 16,
    alignItems: 'center',
  },
  signOutText: { color: '#ef4444', fontWeight: '600' },
});

export default CustomDrawerContent;
