import React, { useState, useEffect } from 'react';
import { View, FlatList, StyleSheet, SafeAreaView, Text, TouchableOpacity, ActivityIndicator, Alert, Image } from 'react-native';
import { supabase } from '../utils/supabase';
import SearchBar from '../components/SearchBar';
import Player from '../components/Player';
import { Download, CheckCircle, Music2 } from 'lucide-react-native';
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

  // 0. SMART CONNECT: Scoperta automatica del Backend
  useEffect(() => {
    const discoverBackend = async () => {
      try {
        const { data, error } = await supabase
          .table('downloads')
          .select('public_url')
          .eq('video_id', 'BACKEND_URL')
          .single();
        
        if (data && data.public_url) {
          console.log(`[SMART CONNECT] Backend scoperto: ${data.public_url}`);
          setBackendUrl(data.public_url);
        }
      } catch (e) {
        console.log('[SMART CONNECT] Uso fallback URL');
      }
    };
    discoverBackend();
  }, []);

  // 1. Supabase Realtime Listener per aggiornamenti di stato
  useEffect(() => {
    const channel = supabase
      .channel('music-downloads')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'downloads' },
        async (payload) => {
          const { video_id, status, public_url } = payload.new;
          if (video_id === 'BACKEND_URL') {
             console.log(`[REALTIME] Nuovo Backend URL ricevuto: ${public_url}`);
             setBackendUrl(public_url);
             return;
          }
          if (status === 'completed' && public_url) {
            await handleSilentDownload(video_id, public_url);
          }
        }
      ).subscribe();
    return () => { supabase.removeChannel(channel); };
  }, []);

  const handleSilentDownload = async (videoId, publicUrl) => {
    const fileUri = `${FileSystem.documentDirectory}${videoId}.mp3`;
    try {
      const { uri } = await FileSystem.downloadAsync(publicUrl, fileUri);
      setOfflineTracks(prev => ({ ...prev, [videoId]: uri }));
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(videoId);
        return next;
      });
    } catch (error) { console.error('Download silenzioso fallito:', error); }
  };

  const onSearch = async (query) => {
    if (!query) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${backendUrl}/search?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      setResults(data.result || []);
    } catch (error) {
      Alert.alert('Errore', 'Impossibile connettersi al Mac. Assicurati che ./avvia-server.sh sia attivo.');
    } finally { setIsLoading(false); }
  };

  const requestDownload = async (item) => {
    const videoId = item.id;
    if (downloadingIds.has(videoId) || offlineTracks[videoId]) return;
    setDownloadingIds(prev => new Set(prev).add(videoId));
    try {
      await fetch(`${backendUrl}/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: videoId, title: item.title })
      });
    } catch (error) {
      Alert.alert('Errore Download', 'Il Mac non risponde. Verifica il server.');
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(videoId);
        return next;
      });
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.header}>
        <Text style={styles.title}>Sopotfy</Text>
        <Text style={styles.subtitle}>Native Turbo Engine 🔥</Text>
      </View>
      <SearchBar onSearch={onSearch} value={searchQuery} onChangeText={setSearchQuery} />
      {isLoading ? (
        <View style={styles.loader}>
          <ActivityIndicator size="large" color="#1DB954" />
        </View>
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
                <Text style={styles.cardChannel}>{item.channel.name}</Text>
              </View>
              <TouchableOpacity onPress={() => offlineTracks[item.id] ? setCurrentTrack(item) : requestDownload(item)}>
                {offlineTracks[item.id] ? (
                  <CheckCircle size={28} color="#1DB954" />
                ) : downloadingIds.has(item.id) ? (
                  <ActivityIndicator size="small" color="#1DB954" />
                ) : (
                  <Download size={28} color="#FFF" />
                )}
              </TouchableOpacity>
            </View>
          )}
        />
      )}
      {currentTrack && (
        <Player track={currentTrack} localUri={offlineTracks[currentTrack.id]} onTitleClick={() => setCurrentTrack(null)} />
      )}
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
  loader: { flex: 1, justifyContent: 'center', alignItems: 'center' }
});

export default HomeScreen;
