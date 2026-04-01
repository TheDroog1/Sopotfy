import React, { useState, useEffect } from 'react';
import { View, FlatList, StyleSheet, SafeAreaView, Text, TouchableOpacity, ActivityIndicator, Alert, Image } from 'react-native';
import { supabase } from '../utils/supabase';
import SearchBar from '../components/SearchBar';
import Player from '../components/Player';
import { Download, CheckCircle } from 'lucide-react-native';
import * as FileSystem from 'expo-file-system';
import { StatusBar } from 'expo-status-bar';

const HomeScreen = () => {
  const [backendUrl, setBackendUrl] = useState('https://absent-lafayette-skills-mineral.trycloudflare.com');
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [offlineTracks, setOfflineTracks] = useState({});
  const [downloadingIds, setDownloadingIds] = useState(new Set());
  const [currentTrack, setCurrentTrack] = useState(null);

  useEffect(() => {
    const discoverBackend = async () => {
      try {
        const { data, error } = await supabase
          .table('downloads')
          .select('file_url')
          .eq('video_id', 'BACKEND_URL')
          .single();
        if (data && data.file_url) {
          console.log(`[SMART CONNECT] Backend: ${data.file_url}`);
          setBackendUrl(data.file_url);
        }
      } catch (e) { /* Fallback */ }
    };
    discoverBackend();
  }, []);

  useEffect(() => {
    const channel = supabase
      .channel('music-updates')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'downloads' },
        async (payload) => {
          const { video_id, status, file_url } = payload.new;
          if (video_id === 'BACKEND_URL' && file_url) {
             setBackendUrl(file_url);
             return;
          }
          if (status === 'completed' && file_url) {
            const fileUri = `${FileSystem.documentDirectory}${video_id}.mp3`;
            await FileSystem.downloadAsync(file_url, fileUri);
            setOfflineTracks(p => ({ ...p, [video_id]: fileUri }));
            setDownloadingIds(p => { const n = new Set(p); n.delete(video_id); return n; });
          }
        }
      ).subscribe();
    return () => { supabase.removeChannel(channel); };
  }, []);

  const onSearch = async (query) => {
    if (!query) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${backendUrl}/search?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      setResults(data.result || []);
    } catch (error) {
      Alert.alert('Errore', 'Connessione al Mac fallita. Aspetta 15s dopo l\'avvio di ./avvia-server.sh');
    } finally { setIsLoading(false); }
  };

  const requestDownload = async (item) => {
    if (downloadingIds.has(item.id) || offlineTracks[item.id]) return;
    setDownloadingIds(p => new Set(p).add(item.id));
    try {
      await fetch(`${backendUrl}/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: item.id, title: item.title })
      });
    } catch (error) {
      setDownloadingIds(p => { const n = new Set(p); n.delete(item.id); return n; });
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Text style={styles.title}>Sopotfy</Text>
        <Text style={styles.subtitle}>Mac Turbo Smart Edition 🔥</Text>
      </View>
      <SearchBar onSearch={onSearch} value={searchQuery} onChangeText={setSearchQuery} />
      {isLoading ? (
        <View style={styles.loader}><ActivityIndicator size="large" color="#1DB954" /></View>
      ) : (
        <FlatList
          data={results}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <Image source={{ uri: item.thumbnails[0].url }} style={styles.thumbnail} />
              <View style={styles.cardInfo}>
                <Text style={styles.cardTitle} numberOfLines={1}>{item.title}</Text>
                <Text style={styles.cardChannel}>{item.channel?.name}</Text>
              </View>
              <TouchableOpacity onPress={() => offlineTracks[item.id] ? setCurrentTrack(item) : requestDownload(item)}>
                {offlineTracks[item.id] ? <CheckCircle size={28} color="#1DB954" /> : downloadingIds.has(item.id) ? <ActivityIndicator size="small" color="#1DB954" /> : <Download size={28} color="#FFF" />}
              </TouchableOpacity>
            </View>
          )}
        />
      )}
      {currentTrack && <Player track={currentTrack} localUri={offlineTracks[currentTrack.id]} onTitleClick={() => setCurrentTrack(null)} />}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#121212' },
  header: { padding: 20, paddingTop: 60 },
  title: { fontSize: 32, fontWeight: 'bold', color: '#FFF' },
  subtitle: { fontSize: 14, color: '#1DB954', marginTop: 4 },
  list: { padding: 15 },
  card: { flexDirection: 'row', backgroundColor: '#1E1E1E', borderRadius: 12, padding: 12, marginBottom: 15, alignItems: 'center' },
  thumbnail: { width: 60, height: 60, borderRadius: 8, marginRight: 15 },
  cardInfo: { flex: 1 },
  cardTitle: { color: '#FFF', fontSize: 16, fontWeight: 'bold' },
  cardChannel: { color: '#AAA', fontSize: 13, marginTop: 4 },
  loader: { flex: 1, justifyContent: 'center' }
});

export default HomeScreen;
