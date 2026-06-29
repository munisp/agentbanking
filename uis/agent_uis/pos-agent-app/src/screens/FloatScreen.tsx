import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, SafeAreaView } from 'react-native';
import { useNavigation } from '@react-navigation/native';

export default function FloatScreen() {
  const navigation = useNavigation<any>();
  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backText}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Float</Text>
      </View>
      <View style={styles.body}>
        <Text style={styles.label}>Float</Text>
        <TouchableOpacity
          style={styles.btn}
          onPress={() => navigation.navigate('FloatManagement')}
        >
          <Text style={styles.btnText}>Open Float Management</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.backLink} onPress={() => navigation.goBack()}>
          <Text style={styles.backLinkText}>Back</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: '#e5e7eb' },
  backBtn: { marginRight: 12 },
  backText: { fontSize: 18, color: '#3b82f6' },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#111827' },
  body: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16 },
  label: { fontSize: 22, fontWeight: '600', color: '#111827' },
  btn: { backgroundColor: '#3b82f6', borderRadius: 10, paddingHorizontal: 24, paddingVertical: 12 },
  btnText: { color: '#fff', fontWeight: '600' },
  backLink: { paddingVertical: 8 },
  backLinkText: { color: '#6b7280', fontSize: 14 },
});
