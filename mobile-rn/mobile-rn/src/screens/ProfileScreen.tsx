import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView, Alert } from 'react-native';
import { WalletService, UserProfile } from '../services/WalletService';
import { AnalyticsService } from '../services/AnalyticsService';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();


export const ProfileScreen = ({ navigation }: any) => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    AnalyticsService.trackScreenView('Profile');
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const data = await WalletService.getUserProfile();
      setProfile(data);
      setName(data.name);
      setEmail(data.email);
      setPhone(data.phone);
    } catch (error) {
      AnalyticsService.trackError('profile_load_failed', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      const updated = await WalletService.updateUserProfile({
        name,
        email,
        phone,
      });
      setProfile(updated);
      setEditing(false);
      AnalyticsService.trackButtonClick('profile_saved');
      Alert.alert('Success', 'Profile updated successfully');
    } catch (error) {
      AnalyticsService.trackError('profile_update_failed', error);
      Alert.alert('Error', 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    if (profile) {
      setName(profile.name);
      setEmail(profile.email);
      setPhone(profile.phone);
    }
    setEditing(false);
  };

  if (loading && !profile) {
    return (
      <View style={styles.loadingContainer}>
        <Text>Loading profile...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {profile?.name.split(' ').map(n => n[0]).join('').toUpperCase()}
          </Text>
        </View>
        <Text style={styles.headerName}>{profile?.name}</Text>
        <View style={[styles.kycBadge, styles[`kyc${profile?.kycStatus.charAt(0).toUpperCase()}${profile?.kycStatus.slice(1)}`]]}>
          <Text style={styles.kycText}>{profile?.kycStatus.toUpperCase()}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Personal Information</Text>

        <View style={styles.field}>
          <Text style={styles.label}>Full Name</Text>
          {editing ? (
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="Enter your name"
            />
          ) : (
            <Text style={styles.value}>{profile?.name}</Text>
          )}
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Email</Text>
          {editing ? (
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="Enter your email"
              keyboardType="email-address"
              autoCapitalize="none"
            />
          ) : (
            <Text style={styles.value}>{profile?.email}</Text>
          )}
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Phone</Text>
          {editing ? (
            <TextInput
              style={styles.input}
              value={phone}
              onChangeText={setPhone}
              placeholder="Enter your phone"
              keyboardType="phone-pad"
            />
          ) : (
            <Text style={styles.value}>{profile?.phone}</Text>
          )}
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Country</Text>
          <Text style={styles.value}>{profile?.country}</Text>
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>Member Since</Text>
          <Text style={styles.value}>{profile?.createdAt}</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Actions</Text>
        
        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionButtonText}>Change Password</Text>
          <Text style={styles.actionButtonIcon}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionButtonText}>Notification Settings</Text>
          <Text style={styles.actionButtonIcon}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionButtonText}>Security Settings</Text>
          <Text style={styles.actionButtonIcon}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionButtonText}>Privacy Policy</Text>
          <Text style={styles.actionButtonIcon}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={[styles.actionButton, styles.actionButtonDanger]}>
          <Text style={[styles.actionButtonText, styles.actionButtonTextDanger]}>Logout</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.buttonContainer}>
        {editing ? (
          <>
            <TouchableOpacity style={styles.btnSecondary} onPress={handleCancel}>
              <Text style={styles.btnSecondaryText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.btnPrimary} onPress={handleSave} disabled={loading}>
              <Text style={styles.btnPrimaryText}>{loading ? 'Saving...' : 'Save'}</Text>
            </TouchableOpacity>
          </>
        ) : (
          <TouchableOpacity style={styles.btnPrimary} onPress={() => setEditing(true)}>
            <Text style={styles.btnPrimaryText}>Edit Profile</Text>
          </TouchableOpacity>
        )}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    backgroundColor: '#FFFFFF',
    padding: 32,
    alignItems: 'center',
  },
  avatar: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#007AFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  avatarText: {
    fontSize: 36,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  headerName: {
    fontSize: 24,
    fontWeight: '600',
    marginBottom: 8,
  },
  kycBadge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  kycVerified: {
    backgroundColor: 'rgba(52, 199, 89, 0.1)',
  },
  kycPending: {
    backgroundColor: 'rgba(255, 149, 0, 0.1)',
  },
  kycRejected: {
    backgroundColor: 'rgba(255, 59, 48, 0.1)',
  },
  kycText: {
    fontSize: 12,
    fontWeight: '600',
  },
  section: {
    backgroundColor: '#FFFFFF',
    padding: 20,
    marginTop: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 16,
  },
  field: {
    marginBottom: 20,
  },
  label: {
    fontSize: 14,
    color: '#8E8E93',
    marginBottom: 8,
  },
  value: {
    fontSize: 16,
    color: '#1C1C1E',
  },
  input: {
    borderWidth: 1,
    borderColor: '#E5E5EA',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  actionButton: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#F2F2F7',
    borderRadius: 8,
    marginBottom: 8,
  },
  actionButtonText: {
    fontSize: 16,
    color: '#1C1C1E',
  },
  actionButtonIcon: {
    fontSize: 24,
    color: '#8E8E93',
  },
  actionButtonDanger: {
    backgroundColor: 'rgba(255, 59, 48, 0.1)',
  },
  actionButtonTextDanger: {
    color: '#FF3B30',
  },
  buttonContainer: {
    flexDirection: 'row',
    padding: 20,
    gap: 12,
  },
  btnPrimary: {
    flex: 1,
    backgroundColor: '#007AFF',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  btnPrimaryText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  btnSecondary: {
    flex: 1,
    backgroundColor: '#F2F2F7',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  btnSecondaryText: {
    color: '#1C1C1E',
    fontSize: 16,
    fontWeight: '600',
  },
});
