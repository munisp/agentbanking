import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image } from 'react-native';
import { AnalyticsService } from '../services/AnalyticsService';
import { APIClient } from '../api/APIClient';
const apiClient = new APIClient();


const ONBOARDING_STEPS = [
  {
    title: 'Send Money Globally',
    description: 'Transfer funds to over 50 countries using multiple payment systems including NIBSS, PAPSS, PIX, UPI, Mojaloop, and CIPS.',
    image: '💸',
  },
  {
    title: 'Secure & Fast',
    description: 'Bank-level security with biometric authentication and instant transfers to most destinations.',
    image: '🔒',
  },
  {
    title: 'Low Fees',
    description: 'Competitive exchange rates and transparent fees. No hidden charges.',
    image: '💰',
  },
  {
    title: 'Track Everything',
    description: 'Real-time transaction tracking and detailed history for all your transfers.',
    image: '📊',
  },
];

export const OnboardingScreen = ({ navigation }: any) => {
  const [currentStep, setCurrentStep] = useState(0);

  React.useEffect(() => {
    AnalyticsService.trackScreenView('Onboarding');
    AnalyticsService.trackEvent('onboarding_started', { step: 0 });
  }, []);

  const handleNext = () => {
    if (currentStep < ONBOARDING_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
      AnalyticsService.trackEvent('onboarding_step_completed', { step: currentStep });
    } else {
      handleComplete();
    }
  };

  const handleSkip = () => {
    AnalyticsService.trackEvent('onboarding_skipped', { step: currentStep });
    handleComplete();
  };

  const handleComplete = () => {
    AnalyticsService.trackEvent('onboarding_completed', { 
      completedSteps: currentStep + 1,
      totalSteps: ONBOARDING_STEPS.length 
    });
    navigation.replace('Dashboard');
  };

  const step = ONBOARDING_STEPS[currentStep];

  return (
    <View style={styles.container}>
      <View style={styles.skipContainer}>
        <TouchableOpacity onPress={handleSkip}>
          <Text style={styles.skipText}>Skip</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.content}>
        <View style={styles.imageContainer}>
          <Text style={styles.emoji}>{step.image}</Text>
        </View>

        <Text style={styles.title}>{step.title}</Text>
        <Text style={styles.description}>{step.description}</Text>
      </View>

      <View style={styles.footer}>
        <View style={styles.pagination}>
          {ONBOARDING_STEPS.map((_, index) => (
            <View
              key={index}
              style={[
                styles.paginationDot,
                index === currentStep && styles.paginationDotActive,
              ]}
            />
          ))}
        </View>

        <TouchableOpacity style={styles.nextButton} onPress={handleNext}>
          <Text style={styles.nextButtonText}>
            {currentStep === ONBOARDING_STEPS.length - 1 ? 'Get Started' : 'Next'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  skipContainer: {
    alignItems: 'flex-end',
    padding: 20,
  },
  skipText: {
    fontSize: 16,
    color: '#007AFF',
    fontWeight: '500',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  imageContainer: {
    width: 200,
    height: 200,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 40,
  },
  emoji: {
    fontSize: 120,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 16,
    color: '#1C1C1E',
  },
  description: {
    fontSize: 16,
    textAlign: 'center',
    color: '#8E8E93',
    lineHeight: 24,
  },
  footer: {
    padding: 40,
  },
  pagination: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 32,
    gap: 8,
  },
  paginationDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#E5E5EA',
  },
  paginationDotActive: {
    backgroundColor: '#007AFF',
    width: 24,
  },
  nextButton: {
    backgroundColor: '#007AFF',
    padding: 18,
    borderRadius: 12,
    alignItems: 'center',
  },
  nextButtonText: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
  },
});
