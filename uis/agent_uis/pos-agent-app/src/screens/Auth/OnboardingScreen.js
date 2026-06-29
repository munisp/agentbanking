import React, { useState } from "react";
import { Image, ScrollView, StyleSheet, View } from "react-native";
import { Button, Text, useTheme } from "react-native-paper";
import { spacing } from "../../theme";
const logo = require("../../../assets/logo.png");

const onboardingSteps = [
  {
    title: "Welcome to Area Konnect by Fidelity Agent Banking",
    description: "Manage your agent banking services efficiently",
    icon: "account-group",
  },
  {
    title: "Track Transactions",
    description: "Monitor all your financial transactions in real-time",
    icon: "chart-line",
  },
  {
    title: "Manage POS Terminals",
    description: "Handle POS devices and orders seamlessly",
    icon: "credit-card-outline",
  },
  {
    title: "Grow Your Network",
    description: "Build and manage your agent hierarchy",
    icon: "account-network",
  },
];

export default function OnboardingScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const theme = useTheme();
  const [currentStep, setCurrentStep] = useState(0);

  const handleNext = () => {
    if (currentStep < onboardingSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      // Complete onboarding
      navigation.navigate("Login");
    }
  };

  const handleSkip = () => {
    navigation.navigate("Login");
  };

  const step = onboardingSteps[currentStep];

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.logoContainer}>
          <Image source={logo} style={styles.logoImage} resizeMode="contain" />
        </View>
        <View style={styles.stepContainer}>
          <View
            style={[
              styles.iconContainer,
              { backgroundColor: theme.colors.primary + "20" },
            ]}
          >
            <Text style={[styles.iconText, { color: theme.colors.primary }]}>
              {currentStep + 1}
            </Text>
          </View>

          <Text variant="headlineMedium" style={styles.title}>
            {step.title}
          </Text>
          <Text variant="bodyLarge" style={styles.description}>
            {step.description}
          </Text>
        </View>

        <View style={styles.pagination}>
          {onboardingSteps.map((_, index) => (
            <View
              key={index}
              style={[
                styles.paginationDot,
                {
                  backgroundColor:
                    index === currentStep
                      ? theme.colors.primary
                      : theme.colors.border,
                  width: index === currentStep ? 24 : 8,
                },
              ]}
            />
          ))}
        </View>
      </ScrollView>

      <View style={styles.footer}>
        {currentStep < onboardingSteps.length - 1 && (
          <Button mode="text" onPress={handleSkip}>
            Skip
          </Button>
        )}
        <Button mode="contained" onPress={handleNext} style={styles.nextButton}>
          {currentStep === onboardingSteps.length - 1 ? "Get Started" : "Next"}
        </Button>
      </View>
    </View>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  content: {
    flexGrow: 1,
    justifyContent: "center",
    padding: spacing.lg,
  },
  logoContainer: {
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  logoImage: {
    width: 180,
    height: 60,
  },
  stepContainer: {
    alignItems: "center",
    marginBottom: spacing.xl,
  },
  iconContainer: {
    width: 120,
    height: 120,
    borderRadius: 60,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.xl,
  },
  iconText: {
    fontSize: 48,
    fontWeight: "bold",
  },
  title: {
    fontWeight: "bold",
    textAlign: "center",
    marginBottom: spacing.md,
  },
  description: {
    textAlign: "center",
    color: "#6B7280",
    paddingHorizontal: spacing.lg,
  },
  pagination: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    marginTop: spacing.xl,
  },
  paginationDot: {
    height: 8,
    borderRadius: 4,
    marginHorizontal: 4,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: "#E5E7EB",
  },
  nextButton: {
    flex: 1,
    marginLeft: spacing.md,
    backgroundColor: colors.secondary,
  },
});
