import React, { useEffect } from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { useNavigation } from '@react-navigation/native';

export default function SplashScreen() {
  const navigation = useNavigation<any>();

  useEffect(() => {
    const timer = setTimeout(() => {
      // AppNavigator already handles auth routing; this screen is a manual entry point.
      // Navigate to Login as default — auth context will redirect if already authenticated.
      navigation.replace('Login');
    }, 1500);
    return () => clearTimeout(timer);
  }, [navigation]);

  return (
    <View style={styles.container}>
      <Text style={styles.icon}>⬛</Text>
      <Text style={styles.title}>54Link POS</Text>
      <Text style={styles.subtitle}>Agent Banking Platform</Text>
      <ActivityIndicator style={styles.loader} color="#fff" />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1A56DB',
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: { fontSize: 64, marginBottom: 24 },
  title: { fontSize: 28, fontWeight: '700', color: '#fff', marginBottom: 8 },
  subtitle: { fontSize: 15, color: 'rgba(255,255,255,0.7)', marginBottom: 48 },
  loader: { marginTop: 0 },
});
