import React from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Linking } from 'react-native';
import { AnalyticsService } from '../services/AnalyticsService';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();


export const HelpScreen = () => {
  React.useEffect(() => {
    AnalyticsService.trackScreenView('Help');
  }, []);

  const handleContactSupport = () => {
    AnalyticsService.trackButtonClick('contact_support');
    Linking.openURL('mailto:support@remittance.com');
  };

  const handleCallSupport = () => {
    AnalyticsService.trackButtonClick('call_support');
    Linking.openURL('tel:+2341234567890');
  };

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Frequently Asked Questions</Text>
        
        <View style={styles.faqItem}>
          <Text style={styles.question}>How do I send money?</Text>
          <Text style={styles.answer}>
            Tap "Send Money" on the dashboard, select a beneficiary, enter the amount, choose a payment system, and confirm.
          </Text>
        </View>

        <View style={styles.faqItem}>
          <Text style={styles.question}>What payment systems are supported?</Text>
          <Text style={styles.answer}>
            We support NIBSS, PAPSS, PIX, UPI, Mojaloop, and CIPS for international transfers.
          </Text>
        </View>

        <View style={styles.faqItem}>
          <Text style={styles.question}>How long do transfers take?</Text>
          <Text style={styles.answer}>
            Most transfers are instant. PAPSS takes 1-2 hours, CIPS takes 2-3 hours.
          </Text>
        </View>

        <View style={styles.faqItem}>
          <Text style={styles.question}>What are the fees?</Text>
          <Text style={styles.answer}>
            Fees vary by payment system: NIBSS (₦50), PAPSS (₦100), PIX (₦75), UPI (₦60), Mojaloop (₦80), CIPS (₦120).
          </Text>
        </View>

        <View style={styles.faqItem}>
          <Text style={styles.question}>Is my money safe?</Text>
          <Text style={styles.answer}>
            Yes! We use bank-level encryption, biometric authentication, and secure storage to protect your funds.
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Contact Support</Text>
        
        <TouchableOpacity style={styles.contactCard} onPress={handleContactSupport}>
          <View style={styles.contactIcon}>
            <Text style={styles.iconText}>✉️</Text>
          </View>
          <View style={styles.contactInfo}>
            <Text style={styles.contactLabel}>Email Support</Text>
            <Text style={styles.contactValue}>support@remittance.com</Text>
          </View>
          <Text style={styles.arrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.contactCard} onPress={handleCallSupport}>
          <View style={styles.contactIcon}>
            <Text style={styles.iconText}>📞</Text>
          </View>
          <View style={styles.contactInfo}>
            <Text style={styles.contactLabel}>Phone Support</Text>
            <Text style={styles.contactValue}>+234 123 456 7890</Text>
          </View>
          <Text style={styles.arrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.contactCard}>
          <View style={styles.contactIcon}>
            <Text style={styles.iconText}>💬</Text>
          </View>
          <View style={styles.contactInfo}>
            <Text style={styles.contactLabel}>Live Chat</Text>
            <Text style={styles.contactValue}>Available 24/7</Text>
          </View>
          <Text style={styles.arrow}>›</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Resources</Text>
        
        <TouchableOpacity style={styles.resourceItem}>
          <Text style={styles.resourceLabel}>User Guide</Text>
          <Text style={styles.arrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.resourceItem}>
          <Text style={styles.resourceLabel}>Video Tutorials</Text>
          <Text style={styles.arrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.resourceItem}>
          <Text style={styles.resourceLabel}>Community Forum</Text>
          <Text style={styles.arrow}>›</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F2F2F7',
  },
  section: {
    backgroundColor: '#FFFFFF',
    marginTop: 16,
    padding: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 16,
  },
  faqItem: {
    marginBottom: 20,
  },
  question: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  answer: {
    fontSize: 14,
    color: '#8E8E93',
    lineHeight: 20,
  },
  contactCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#F2F2F7',
    borderRadius: 12,
    marginBottom: 12,
  },
  contactIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  iconText: {
    fontSize: 20,
  },
  contactInfo: {
    flex: 1,
  },
  contactLabel: {
    fontSize: 16,
    fontWeight: '500',
    marginBottom: 2,
  },
  contactValue: {
    fontSize: 14,
    color: '#8E8E93',
  },
  arrow: {
    fontSize: 24,
    color: '#C7C7CC',
  },
  resourceItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#F2F2F7',
  },
  resourceLabel: {
    fontSize: 16,
  },
});
