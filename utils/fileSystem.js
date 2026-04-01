import * as FileSystem from 'expo-file-system';

/**
 * Ensures the directory exists.
 */
export const ensureDirectoryExists = async (directory) => {
  const dirInfo = await FileSystem.getInfoAsync(directory);
  if (!dirInfo.exists) {
    await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  }
};

/**
 * Downloads a file to local storage.
 */
export const downloadFile = async (url, filename) => {
  const fileUri = `${FileSystem.documentDirectory}${filename}`;
  const downloadResumable = FileSystem.createDownloadResumable(
    url,
    fileUri,
    {}
  );

  try {
    const { uri } = await downloadResumable.downloadAsync();
    return uri;
  } catch (e) {
    console.error('Download error:', e);
    return null;
  }
};
