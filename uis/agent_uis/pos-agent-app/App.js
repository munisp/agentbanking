import { StatusBar } from "expo-status-bar";
import React from "react";
import { NativeModules } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { Provider as PaperProvider } from "react-native-paper";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AuthProvider } from "./src/contexts/AuthContext";
import { NotificationProvider } from "./src/contexts/NotificationContext";
import { ThemeProvider, useTheme } from "./src/contexts/ThemeContext";
import AppNavigator from "./src/navigation/AppNavigator";
import { theme as defaultTheme } from "./src/theme";
const { NexgoModule } = NativeModules;

function DynamicPaperProvider({ children }) {
  const { paperTheme } = useTheme();
  return <PaperProvider theme={paperTheme || defaultTheme}>{children}</PaperProvider>;
}

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          <DynamicPaperProvider>
            <AuthProvider>
              <NotificationProvider>
                <AppNavigator />
                <StatusBar style="auto" />
              </NotificationProvider>
            </AuthProvider>
          </DynamicPaperProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
