import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ServerUrlProvider } from './context/ServerUrlContext';
import WebViewScreen from './screens/WebViewScreen';
import ConfigScreen from './screens/ConfigScreen';
import QRScannerScreen from './screens/QRScannerScreen';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <ServerUrlProvider>
      <NavigationContainer>
        <Stack.Navigator
          screenOptions={{
            headerStyle: { backgroundColor: '#000' },
            headerTintColor: '#06C167',
            headerTitleStyle: { fontWeight: 'bold' },
          }}
        >
          <Stack.Screen
            name="Home"
            component={WebViewScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="QRScanner"
            component={QRScannerScreen}
            options={{
              headerShown: false,
              animation: 'slide_from_bottom',
              presentation: 'fullScreenModal',
            }}
          />
          <Stack.Screen
            name="Config"
            component={ConfigScreen}
            options={{
              title: 'Configuración',
              presentation: 'modal',
              headerShown: true,
            }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </ServerUrlProvider>
  );
}
