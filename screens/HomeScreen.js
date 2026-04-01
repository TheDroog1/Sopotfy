import React, { useState, useEffect } from 'react';
import { 
  View, 
  FlatList, 
  StyleSheet, 
  SafeAreaView, 
  Text, 
  TouchableOpacity, 
  ActivityIndicator, 
  Alert,
  Image
} from 'react-native';
import { supabase } from '../utils/supabase';
import SearchBar from '../components/SearchBar';
import Player from '../components/Player';
import { Download, CheckCircle, Music2 } from 'lucide-react-native';
import * as FileSystem from 'expo-file-system';
import { StatusBar } from 'expo-status-bar';

const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL;

const HomeScreen = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [offlineTracks, setOfflineTracks] = useState({}); // { videoId: localUri }
  const [downloadingIds, setDownloadingIds] = useState(new Set());
  const [currentTrack, setCurrentTrack] = useState(null);

  // 1. Supabase Realtime Listener per aggiornamenti di stato
  useEffect(() => {
    const channel = supabase
      .channel('music-downloads')
      .on(
        'postgres_changes',
        {
          event: '*', // Monitoriamo tutti i cambiamenti
          schema: 'public',
          table: 'downloads',
        },
        async (payload) => {
          const { video_id, status, public_url } = payload.new;
          if (status === 'completed' && public_url) {
            await handleSilentDownload(video_id, public_url);
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  // 2. Download silenzioso del file MP3 nel FileSystem locale
  const handleSilentDownload = async (videoId, publicUrl) => {
    const fileUri = `${FileSystem.documentDirectory}${videoId}.mp3`;
    try {
      const { uri } = await FileSystem.downloadAsync(publicUrl, fileUri);
      
      // Aggiorna lo stato dei brani offline
      setOfflineTracks(prev => ({ ...prev, [videoId]: uri }));
      
      // Rimuovi dalla lista dei download in corso
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(videoId);
        return next;
      });
      
      console.log(`File salvato offline: ${uri}`);
    } catch (error) {
      console.error('Download silenzioso fallito:', error);
    }
  };

  // 3. Chiamata al backend per la ricerca
  const onSearch = async (query) => {
    if (!query) return;
    setIsLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/search?q=${encodeURIComponent(query)}`);
      const data = await response.json();
      setResults(data.result || []);
    } catch (error) {
      Alert.alert('Errore', 'Impossibile connettersi al backend. Assicurati che il server sia attivo.');
      console.error(error);
    } finally {
      setIsLoading(false);
    }
  };

  // 4. Gestione del clic sul tasto Download
  const requestDownload = async (item) => {
    const videoId = item.id;
    if (offlineTracks[videoId]) {
      // Se è già offline, mandalo in riproduzione
      setCurrentTrack({ ...item, localUri: offlineTracks[videoId] });
      return;
    }

    setDownloadingIds(prev => new Set(prev).add(videoId));
    
    try {
      // a. Crea record 'pending' su Supabase
      await supabase.table('downloads').upsert({
        video_id: videoId,
        status: 'pending',
        title: item.title
      });

      // b. Invia richiesta di download al backend
      const response = await fetch(`${BACKEND_URL}/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: videoId })
      });

      if (!response.ok) throw new Error('Errore backend');
      
    } catch (error) {
      setDownloadingIds(prev => {
        const next = new Set(prev);
        next.delete(videoId);
        return next;
      });
      Alert.alert('Errore', 'Impossibile avviare il download del brano.');
    }
  };

  const renderResultItem = ({ item }) => {
    const videoId = item.id;
    const isOffline = !!offlineTracks[videoId];
    const isDownloading = downloadingIds.has(videoId);
    const thumbnail = item.thumbnails?.[0]?.url;

    return (
      <TouchableOpacity 
        style={styles.itemContainer}
        onPress={() => isOffline && setCurrentTrack({ ...item, localUri: offlineTracks[videoId] })}
      >
        <Image source={{ uri: thumbnail }} style={styles.thumbnail} />
        <View style={styles.itemInfo}>
          <Text style={styles.itemTitle} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.itemChannel}>{item.channel?.name || 'YouTube'}</Text>
          <View style={styles.badgeContainer}>
            {isOffline && (
              <View style={styles.offlineBadge}>
                <CheckCircle size={12} color="#FFF" />
                <Text style={styles.offlineText}>OFFLINE</Text>
              </View>
            )}
          </View>
        </View>
        
        <TouchableOpacity 
          onPress={() => requestDownload(item)}
          disabled={isDownloading || isOffline}
          style={styles.actionButton}
        >
          {isOffline ? (
            <CheckCircle size={28} color="#1DB954" />
          ) : isDownloading ? (
            <ActivityIndicator size="small" color="#000" />
          ) : (
            <View style={styles.downloadCircle}>
              <Download size={18} color="#000" />
            </View>
          )}
        </TouchableOpacity>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <Text style={styles.title}>Sopotfy</Text>
        <SearchBar 
          value={searchQuery} 
          onChangeText={setSearchQuery}
          onSearch={onSearch}
        />
      </View>

      <FlatList
        data={results}
        keyExtractor={(item) => item.id}
        renderItem={renderResultItem}
        ListEmptyComponent={
          isLoading ? (
            <View style={styles.centered}><ActivityIndicator size="large" /></View>
          ) : (
            <View style={styles.emptyContainer}>
              <Music2 size={80} color="#F0F0F0" />
              <Text style={styles.emptyText}>Cerca i tuoi brani preferiti</Text>
              <Text style={styles.emptySub}>Verranno salvati offline per sempre.</Text>
            </View>
          )
        }
        contentContainerStyle={[styles.listContent, { paddingBottom: currentTrack ? 140 : 20 }]}
        showsVerticalScrollIndicator={false}
      />
      
      <Player track={currentTrack} />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  header: {
    paddingBottom: 15,
  },
  title: {
    fontSize: 34,
    fontWeight: '900',
    paddingHorizontal: 20,
    marginTop: 15,
    letterSpacing: -1,
  },
  listContent: {
    paddingHorizontal: 20,
    flexGrow: 1,
  },
  itemContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#F0F0F0',
  },
  thumbnail: {
    width: 60,
    height: 60,
    borderRadius: 8,
    backgroundColor: '#F0F0F0',
  },
  itemInfo: {
    flex: 1,
    marginLeft: 15,
    justifyContent: 'center',
  },
  itemTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#000',
  },
  itemChannel: {
    fontSize: 14,
    color: '#888',
    marginTop: 2,
  },
  actionButton: {
    padding: 10,
  },
  downloadCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#F0F0F0',
    justifyContent: 'center',
    alignItems: 'center',
  },
  centered: {
    marginTop: 100,
    alignItems: 'center',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 100,
  },
  emptyText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#333',
    marginTop: 20,
  },
  emptySub: {
    fontSize: 14,
    color: '#999',
    marginTop: 5,
  },
  badgeContainer: {
    flexDirection: 'row',
    marginTop: 5,
  },
  offlineBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1DB954',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  offlineText: {
    fontSize: 10,
    fontWeight: '900',
    color: '#FFF',
    marginLeft: 3,
  },
});

export default HomeScreen;
