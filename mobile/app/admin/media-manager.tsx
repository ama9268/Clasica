import { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity,
  ScrollView, Alert, ActivityIndicator, Image,
  TextInput,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { getEdition, addMedia, deleteMedia } from '@/api/editions';
import type { EditionMedia } from '@/types';

export default function MediaManagerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [media, setMedia] = useState<EditionMedia[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  
  const [caption, setCaption] = useState('');
  const [videoUrl, setVideoUrl] = useState('');

  useEffect(() => {
    loadMedia();
  }, [id]);

  async function loadMedia() {
    try {
      const e = await getEdition(Number(id));
      setMedia(e.media || []);
    } catch {
      Alert.alert('Error', 'No se pudo cargar la galería.');
    } finally {
      setLoading(false);
    }
  }

  async function handleAddPhoto() {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.8,
    });

    if (!result.canceled) {
      setUploading(true);
      const fd = new FormData();
      fd.append('media_type', 'photo');
      fd.append('caption', caption);
      fd.append('photo', {
        uri: result.assets[0].uri,
        name: 'photo.jpg',
        type: 'image/jpeg',
      } as any);

      try {
        await addMedia(Number(id), fd);
        setCaption('');
        loadMedia();
      } catch {
        Alert.alert('Error', 'No se pudo subir la foto.');
      } finally {
        setUploading(false);
      }
    }
  }

  async function handleAddVideo() {
    if (!videoUrl) return;
    setUploading(true);
    const fd = new FormData();
    fd.append('media_type', 'video');
    fd.append('caption', caption);
    fd.append('video_url', videoUrl);

    try {
      await addMedia(Number(id), fd);
      setCaption('');
      setVideoUrl('');
      loadMedia();
    } catch {
      Alert.alert('Error', 'No se pudo añadir el vídeo.');
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(mediaId: number) {
    Alert.alert('Eliminar', '¿Seguro que quieres borrar este elemento?', [
      { text: 'Cancelar', style: 'cancel' },
      { 
        text: 'Eliminar', 
        style: 'destructive', 
        onPress: async () => {
          try {
            await deleteMedia(mediaId);
            loadMedia();
          } catch {
            Alert.alert('Error', 'No se pudo eliminar.');
          }
        }
      },
    ]);
  }

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color="#8b1a1a" size="large" />
      </View>
    );
  }

  return (
    <View style={s.container}>
      <ScrollView contentContainerStyle={{ padding: 20 }}>
        <Text style={s.title}>GESTIÓN DE MEDIA</Text>
        
        <View style={s.uploadBox}>
          <Text style={s.label}>Leyenda / Pie de foto</Text>
          <TextInput 
            style={s.input} 
            value={caption} 
            onChangeText={setCaption} 
            placeholder="Opcional..."
          />

          <View style={s.btnRow}>
            <TouchableOpacity style={s.addPhotoBtn} onPress={handleAddPhoto} disabled={uploading}>
              <Ionicons name="camera-outline" size={20} color="#f5f0e8" />
              <Text style={s.addBtnText}>SUBIR FOTO</Text>
            </TouchableOpacity>
          </View>

          <View style={{ marginTop: 16 }}>
            <Text style={s.label}>URL de Vídeo (YouTube/Vimeo)</Text>
            <View style={s.videoInputRow}>
              <TextInput 
                style={[s.input, { flex: 1 }]} 
                value={videoUrl} 
                onChangeText={setVideoUrl} 
                placeholder="https://..."
              />
              <TouchableOpacity style={s.addVideoBtn} onPress={handleAddVideo} disabled={uploading}>
                <Ionicons name="add" size={24} color="#f5f0e8" />
              </TouchableOpacity>
            </View>
          </View>
          
          {uploading && <ActivityIndicator color="#8b1a1a" style={{ marginTop: 10 }} />}
        </View>

        <Text style={s.sectionTitle}>ELEMENTOS ACTUALES ({media.length})</Text>
        <View style={s.grid}>
          {media.map(m => (
            <View key={m.id} style={s.mediaCard}>
              {m.media_type === 'photo' ? (
                <Image source={{ uri: m.photo || '' }} style={s.preview} />
              ) : (
                <View style={[s.preview, s.videoPreview]}>
                  <Ionicons name="play-circle-outline" size={32} color="#f5f0e8" />
                </View>
              )}
              <View style={s.cardInfo}>
                <Text style={s.cardCaption} numberOfLines={1}>
                  {m.caption || (m.media_type === 'photo' ? 'Foto' : 'Vídeo')}
                </Text>
                <TouchableOpacity onPress={() => handleDelete(m.id)}>
                  <Ionicons name="trash-outline" size={18} color="#dc2626" />
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  title: { fontSize: 18, fontWeight: '800', color: '#1a2744', letterSpacing: 1, marginBottom: 20 },
  uploadBox: { backgroundColor: '#fff', padding: 16, borderWidth: 1, borderColor: '#e5e7eb', marginBottom: 24 },
  label: { fontSize: 11, fontWeight: '700', color: '#6b7280', letterSpacing: 1, marginBottom: 6, textTransform: 'uppercase' },
  input: { backgroundColor: '#f9fafb', padding: 12, fontSize: 14, color: '#1a1a1a', borderWidth: 1, borderColor: '#e5e7eb', marginBottom: 12 },
  btnRow: { flexDirection: 'row', gap: 10 },
  addPhotoBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#1a2744', padding: 14 },
  addVideoBtn: { backgroundColor: '#1a2744', padding: 10, justifyContent: 'center' },
  addBtnText: { color: '#f5f0e8', fontSize: 12, fontWeight: '700', letterSpacing: 1 },
  videoInputRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  sectionTitle: { fontSize: 11, fontWeight: '700', color: '#6b7280', letterSpacing: 2, marginBottom: 12 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  mediaCard: { width: '47%', backgroundColor: '#fff', borderWidth: 1, borderColor: '#e5e7eb' },
  preview: { width: '100%', height: 120, backgroundColor: '#e5e7eb' },
  videoPreview: { justifyContent: 'center', alignItems: 'center', backgroundColor: '#1a2744' },
  cardInfo: { padding: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  cardCaption: { fontSize: 11, color: '#4b5563', flex: 1, marginRight: 4 },
});
