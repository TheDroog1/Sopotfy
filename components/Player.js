import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { Play, Pause, Music } from 'lucide-react-native';
import { Audio } from 'expo-av';

const Player = ({ track }) => {
  const [sound, setSound] = useState();
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  async function loadAndPlay() {
    if (!track?.localUri) return;
    
    setIsLoading(true);
    try {
      if (sound) {
        await sound.unloadAsync();
      }

      const { sound: newSound } = await Audio.Sound.createAsync(
        { uri: track.localUri },
        { shouldPlay: true }
      );
      
      setSound(newSound);
      setIsPlaying(true);
      
      newSound.setOnPlaybackStatusUpdate((status) => {
        if (status.didJustFinish) {
          setIsPlaying(false);
        }
      });
    } catch (error) {
      console.error('Error loading sound', error);
    } finally {
      setIsLoading(false);
    }
  }

  async function togglePlayback() {
    if (!sound) {
      await loadAndPlay();
      return;
    }

    if (isPlaying) {
      await sound.pauseAsync();
      setIsPlaying(false);
    } else {
      await sound.playAsync();
      setIsPlaying(true);
    }
  }

  useEffect(() => {
    // When track changes, load new sound
    if (track?.localUri) {
        loadAndPlay();
    }
    
    return () => {
      if (sound) {
        sound.unloadAsync();
      }
    };
  }, [track]);

  if (!track) return null;

  return (
    <View style={styles.container}>
      <View style={styles.content}>
        <Music size={24} color="#000" />
        <View style={styles.info}>
          <Text style={styles.title} numberOfLines={1}>{track.title}</Text>
          <Text style={styles.status}>Offline Mode</Text>
        </View>
        <TouchableOpacity onPress={togglePlayback} style={styles.playButton}>
          {isLoading ? (
            <ActivityIndicator color="#000" />
          ) : isPlaying ? (
            <Pause size={32} fill="#000" color="#000" />
          ) : (
            <Play size={32} fill="#000" color="#000" />
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: '#FFF',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#DDD',
    paddingBottom: 20, // SafeArea spacing
    paddingHorizontal: 20,
    paddingTop: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: -2 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 20,
  },
  content: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  info: {
    flex: 1,
    marginLeft: 15,
  },
  title: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  status: {
    fontSize: 12,
    color: '#666',
  },
  playButton: {
    padding: 10,
  },
});

export default Player;
