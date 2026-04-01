import { Audio } from 'expo-av';

let sound = null;

/**
 * Loads and plays audio from a given source (URI or local asset).
 */
export const playAudio = async (uri) => {
  try {
    if (sound) {
      await sound.unloadAsync();
    }

    const { sound: newSound } = await Audio.Sound.createAsync(
      { uri },
      { shouldPlay: true }
    );
    sound = newSound;
  } catch (error) {
    console.error('Playback Error:', error);
  }
};

/**
 * Stops playback and unloads from memory.
 */
export const stopAudio = async () => {
  if (sound) {
    await sound.stopAsync();
    await sound.unloadAsync();
    sound = null;
  }
};
