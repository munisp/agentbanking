/**
 * SelectProvider Screen
 * Journey: Airtime/Data Top-up
 * ID: journey_09_airtime_topup
 *
 * Displays Nigerian network providers (MTN, Airtel, Glo, 9mobile).
 * Navigates to EnterPhoneScreen with the selected provider.
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import * as Haptics from 'expo-haptics';
import { APIClient } from '../../api/APIClient';
const apiClient = new APIClient();


interface Provider {
  id: string;
  name: string;
  color: string;
  prefixes: string;
}

const PROVIDERS: Provider[] = [
  { id: 'mtn',     name: 'MTN',     color: '#FFCC00', prefixes: '0803, 0806, 0813, 0816, 0703, 0706' },
  { id: 'airtel',  name: 'Airtel',  color: '#FF0000', prefixes: '0802, 0808, 0812, 0701, 0708' },
  { id: 'glo',     name: 'Glo',     color: '#00A651', prefixes: '0805, 0807, 0815, 0811, 0705' },
  { id: '9mobile', name: '9mobile', color: '#006633', prefixes: '0809, 0817, 0818, 0909, 0908' },
];

interface SelectProviderScreenProps {
  navigation: any;
  route: any;
}

export const SelectProviderScreen: React.FC<SelectProviderScreenProps> = ({ navigation }) => {
  const [selected, setSelected] = useState<string | null>(null);

  const handleSelect = async (provider: Provider) => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSelected(provider.id);
  };

  const handleContinue = async () => {
    if (!selected) return;
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    const provider = PROVIDERS.find(p => p.id === selected)!;
    navigation.navigate('EnterPhone', { provider });
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Airtime Top-up</Text>
      <Text style={styles.subtitle}>Select your network provider</Text>

      <View style={styles.grid}>
        {PROVIDERS.map(provider => (
          <TouchableOpacity
            key={provider.id}
            style={[
              styles.providerCard,
              selected === provider.id && { borderColor: provider.color, backgroundColor: '#F0F8FF' },
            ]}
            onPress={() => handleSelect(provider)}
            activeOpacity={0.7}
          >
            <View style={[styles.providerLogo, { backgroundColor: provider.color }]}>
              <Text style={styles.providerLogoText}>{provider.name[0]}</Text>
            </View>
            <Text style={styles.providerName}>{provider.name}</Text>
            {selected === provider.id && (
              <View style={[styles.checkBadge, { backgroundColor: provider.color }]}>
                <Text style={styles.checkText}>✓</Text>
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {selected && (
        <View style={styles.hint}>
          <Text style={styles.hintText}>
            {PROVIDERS.find(p => p.id === selected)?.name} prefixes:{' '}
            {PROVIDERS.find(p => p.id === selected)?.prefixes}
          </Text>
        </View>
      )}

      <TouchableOpacity
        style={[styles.primaryButton, !selected && styles.primaryButtonDisabled]}
        onPress={handleContinue}
        disabled={!selected}
      >
        <Text style={styles.buttonText}>Continue</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#FFFFFF' },
  content: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 28, fontWeight: 'bold', color: '#1C1C1E', marginBottom: 6 },
  subtitle: { fontSize: 15, color: '#8E8E93', marginBottom: 28 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginBottom: 20 },
  providerCard: {
    width: '47%',
    borderWidth: 2,
    borderColor: '#E5E5EA',
    borderRadius: 16,
    padding: 20,
    alignItems: 'center',
    backgroundColor: '#FAFAFA',
    position: 'relative',
  },
  providerLogo: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  providerLogoText: { fontSize: 24, fontWeight: 'bold', color: '#FFFFFF' },
  providerName: { fontSize: 16, fontWeight: '600', color: '#1C1C1E' },
  checkBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkText: { color: '#FFFFFF', fontSize: 12, fontWeight: 'bold' },
  hint: { backgroundColor: '#F2F2F7', borderRadius: 10, padding: 12, marginBottom: 20 },
  hintText: { fontSize: 13, color: '#636366', lineHeight: 18 },
  primaryButton: { backgroundColor: '#0066FF', padding: 16, borderRadius: 14, alignItems: 'center', marginTop: 8 },
  primaryButtonDisabled: { backgroundColor: '#C7C7CC' },
  buttonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '600' },
});
