import React, { useState } from "react";
import {
    Image,
    KeyboardAvoidingView,
    Platform,
    ScrollView,
    StyleSheet,
    View,
} from "react-native";
import {
    Button,
    Snackbar,
    Text,
    TextInput,
    useTheme} from "react-native-paper";
import { useAuth } from "../../contexts/AuthContext";
import { spacing } from "../../theme";
const logo = require("../../../assets/logo.png");

export default function LoginScreen({
 navigation }) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async () => {
    setLoading(true);
    setError("");
    try {
      await login(email, password);
    } catch (error) {
      const errorMsg =
        error?.message?.detail || String(error) || "Login failed";
      console.error("Login failed:", errorMsg);
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.logoContainer}>
          <Image source={logo} style={styles.logoImage} resizeMode="contain" />
          <Text style={styles.subtitle}>Agent Banking Dashboard</Text>
        </View>

        <View style={styles.formContainer}>
          <Text variant="headlineSmall" style={styles.title}>
            Welcome Back
          </Text>
          <Text variant="bodyMedium" style={styles.description}>
            Sign in to continue
          </Text>

          <TextInput
            label="Email"
            value={email}
            onChangeText={setEmail}
            mode="outlined"
            keyboardType="email-address"
            autoCapitalize="none"
            style={styles.input}
            left={<TextInput.Icon icon="email" />}
          />

          <TextInput
            label="Password"
            value={password}
            onChangeText={setPassword}
            mode="outlined"
            secureTextEntry={!showPassword}
            style={styles.input}
            left={<TextInput.Icon icon="lock" />}
            right={
              <TextInput.Icon
                icon={showPassword ? "eye-off" : "eye"}
                onPress={() => setShowPassword(!showPassword)}
              />
            }
          />

          <Button
            mode="contained"
            onPress={handleLogin}
            loading={loading}
            disabled={loading || !email || !password}
            style={styles.button}
          >
            Sign In
          </Button>

          {/* <View style={styles.signupContainer}>
            <Text variant="bodyMedium">Don't have an account? </Text>
            <Button
              mode="text"
              onPress={() => navigation.navigate("SignUp")}
              compact
            >
              Sign Up
            </Button>
          </View> */}
        </View>
      </ScrollView>

      <Snackbar
        visible={!!error}
        onDismiss={() => setError("")}
        duration={4000}
        action={{
          label: "Dismiss",
          onPress: () => setError(""),
        }}
      >
        {error}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const makeStyles = (colors) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#fff",
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    padding: spacing.lg,
  },
  logoContainer: {
    alignItems: "center",
    marginBottom: spacing.xl,
  },
  logoImage: {
    width: 180,
    height: 60,
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontSize: 16,
    color: "#6B7280",
    marginTop: spacing.sm,
  },
  formContainer: {
    width: "100%",
  },
  title: {
    fontWeight: "bold",
    marginBottom: spacing.sm,
    textAlign: "center",
  },
  description: {
    color: "#6B7280",
    marginBottom: spacing.lg,
    textAlign: "center",
  },
  input: {
    marginBottom: spacing.md,
  },
  button: {
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.primary,
  },
  signupContainer: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    marginTop: spacing.lg,
  },
});
