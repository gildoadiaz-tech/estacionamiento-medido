import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  SafeAreaView,
  Alert,
} from 'react-native';
import { useServerUrl } from '../context/ServerUrlContext';

export default function ConfigScreen({ navigation }) {
  const { serverUrl, updateUrl } = useServerUrl();
  const [url, setUrl] = useState(serverUrl);

  const handleSave = async () => {
    const trimmed = url.trim().replace(/\/+$/, '');
    if (!trimmed) {
      Alert.alert('Error', 'Ingresá una URL válida');
      return;
    }
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      Alert.alert('Error', 'La URL debe comenzar con http:// o https://');
      return;
    }
    await updateUrl(trimmed);
    Alert.alert('Guardado', 'URL actualizada correctamente', [
      { text: 'OK', onPress: () => navigation.goBack() },
    ]);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <Text style={styles.label}>URL del servidor</Text>
        <TextInput
          style={styles.input}
          value={url}
          onChangeText={setUrl}
          placeholder="http://localhost:8000"
          placeholderTextColor="#555"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />
        <Text style={styles.hint}>
          Ingresá la URL del servidor de estacionamiento.{'\n'}
          Ej: https://tunel.cloudflared.com
        </Text>

        <TouchableOpacity style={styles.button} onPress={handleSave}>
          <Text style={styles.buttonText}>Guardar</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111',
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 32,
  },
  label: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#1a1a1a',
    borderWidth: 1,
    borderColor: '#333',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: '#fff',
    fontSize: 16,
  },
  hint: {
    color: '#888',
    fontSize: 13,
    marginTop: 12,
    lineHeight: 20,
  },
  button: {
    backgroundColor: '#06C167',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginTop: 32,
  },
  buttonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '700',
  },
});
