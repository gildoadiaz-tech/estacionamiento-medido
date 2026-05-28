import React, { createContext, useContext, useState, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = '@server_url';
const DEFAULT_URL = 'http://localhost:8000';

const ServerUrlContext = createContext();

export function ServerUrlProvider({ children }) {
  const [serverUrl, setServerUrl] = useState(DEFAULT_URL);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then((stored) => {
      if (stored) setServerUrl(stored);
      setLoaded(true);
    });
  }, []);

  const updateUrl = async (url) => {
    setServerUrl(url);
    await AsyncStorage.setItem(STORAGE_KEY, url);
  };

  return (
    <ServerUrlContext.Provider value={{ serverUrl, updateUrl, loaded }}>
      {children}
    </ServerUrlContext.Provider>
  );
}

export function useServerUrl() {
  return useContext(ServerUrlContext);
}
