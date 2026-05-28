import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  SafeAreaView,
  StatusBar,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { useServerUrl } from '../context/ServerUrlContext';

export default function WebViewScreen({ navigation, route }) {
  const { serverUrl, loaded } = useServerUrl();
  const webviewRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const baseUrl = serverUrl.replace(/\/+$/, '');
  const [currentPath, setCurrentPath] = useState('/conductor/login');

  const uri = `${baseUrl}${currentPath}`;

  useEffect(() => {
    if (route.params?.scanPath) {
      const path = route.params.scanPath;
      setCurrentPath(path);
      setLoading(true);
      setError(null);
      // Clear the param so it doesn't re-trigger on re-render
      navigation.setParams({ scanPath: undefined });
    }
  }, [route.params?.scanPath]);

  const handleError = (syntheticEvent) => {
    const { description } = syntheticEvent.nativeEvent;
    setError(description || 'Error de conexión');
    setLoading(false);
  };

  const handleLoadEnd = () => {
    setLoading(false);
    setError(null);
  };

  const handleNavigationStateChange = (navState) => {
    if (navState.url && navState.url.startsWith(baseUrl)) {
      const path = navState.url.replace(baseUrl, '') || '/';
      setCurrentPath(path);
    }
  };

  const reload = () => {
    setLoading(true);
    setError(null);
    webviewRef.current?.reload();
  };

  const openQRScanner = () => {
    navigation.navigate('QRScanner');
  };

  if (!loaded) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator color="#06C167" size="large" />
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor="#000" />
        <View style={styles.errorContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorTitle}>Error de conexión</Text>
          <Text style={styles.errorText}>{error}</Text>
          <Text style={styles.errorHint}>
            Verificá que el servidor esté corriendo en:{'\n'}
            {serverUrl}
          </Text>
          <View style={styles.errorButtons}>
            <TouchableOpacity style={styles.button} onPress={reload}>
              <Text style={styles.buttonText}>Reintentar</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.button, styles.buttonOutline]}
              onPress={() => navigation.navigate('Config')}
            >
              <Text style={[styles.buttonText, styles.buttonOutlineText]}>
                Cambiar URL
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#000" />
      <WebView
        ref={webviewRef}
        source={{ uri }}
        style={styles.webview}
        onError={handleError}
        onLoadEnd={handleLoadEnd}
        onNavigationStateChange={handleNavigationStateChange}
        javaScriptEnabled
        domStorageEnabled
        startInLoadingState
        allowsBackForwardNavigationGestures
        allowsInlineMediaPlayback
        mediaPlaybackRequiresUserAction={false}
        renderLoading={() => (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator color="#06C167" size="large" />
            <Text style={styles.loadingText}>Cargando...</Text>
          </View>
        )}
      />
      <TouchableOpacity
        style={styles.gearButton}
        onPress={() => navigation.navigate('Config')}
      >
        <Text style={styles.gearIcon}>⚙️</Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.qrButton} onPress={openQRScanner}>
        <Text style={styles.qrIcon}>◻</Text>
        <Text style={styles.qrLabel}>Escanear QR</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
  },
  webview: {
    flex: 1,
    backgroundColor: '#000',
  },
  loadingOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#000',
  },
  loadingText: {
    color: '#06C167',
    marginTop: 12,
    fontSize: 14,
  },
  gearButton: {
    position: 'absolute',
    top: 50,
    right: 16,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#06C167',
  },
  gearIcon: {
    fontSize: 20,
  },
  qrButton: {
    position: 'absolute',
    bottom: 32,
    alignSelf: 'center',
    backgroundColor: '#06C167',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 28,
    gap: 8,
    elevation: 8,
    shadowColor: '#06C167',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
  },
  qrIcon: {
    fontSize: 20,
    color: '#000',
  },
  qrLabel: {
    color: '#000',
    fontSize: 16,
    fontWeight: '700',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  errorTitle: {
    color: '#fff',
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  errorText: {
    color: '#ff4444',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 8,
  },
  errorHint: {
    color: '#888',
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 24,
  },
  errorButtons: {
    gap: 12,
  },
  button: {
    backgroundColor: '#06C167',
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 8,
  },
  buttonOutline: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#06C167',
  },
  buttonText: {
    color: '#000',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonOutlineText: {
    color: '#06C167',
  },
});
