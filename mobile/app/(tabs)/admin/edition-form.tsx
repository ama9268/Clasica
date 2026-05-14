import { useEffect, useState } from 'react';
import {
  View, Text, TextInput, StyleSheet, TouchableOpacity,
  ScrollView, Alert, ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as DocumentPicker from 'expo-document-picker';
import { getEdition, createEdition, updateEdition, getRouteVariants } from '@/api/editions';
import type { RouteVariant } from '@/types';

export default function EditionFormScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const isEdit = !!id;
  const router = useRouter();

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [variants, setVariants] = useState<RouteVariant[]>([]);
  
  const [name, setName] = useState('');
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [startTime, setStartTime] = useState('16:30:00');
  const [status, setStatus] = useState<'open' | 'closed' | 'results_published'>('open');
  const [variantId, setVariantId] = useState<number | null>(null);
  const [gpxFile, setGpxFile] = useState<any>(null);

  useEffect(() => {
    getRouteVariants().then(setVariants).catch(console.error);

    if (isEdit) {
      getEdition(Number(id))
        .then(e => {
          setName(e.name);
          setDate(e.date);
          setStartTime(e.start_time);
          setStatus(e.status);
          // Note: Edition detail should probably return variant ID if we want to pre-select
        })
        .catch(() => Alert.alert('Error', 'No se pudo cargar la edición.'))
        .finally(() => setLoading(false));
    }
  }, [id]);

  async function pickGPX() {
    const res = await DocumentPicker.getDocumentAsync({
      type: ['application/gpx+xml', '*/*'],
      copyToCacheDirectory: true,
    });
    if (!res.canceled) {
      setGpxFile(res.assets[0]);
    }
  }

  async function handleSave() {
    if (!name || !date) {
      return Alert.alert('Campos requeridos', 'Por favor rellena nombre y fecha.');
    }

    setSaving(true);
    const fd = new FormData();
    fd.append('name', name);
    fd.append('date', date);
    fd.append('start_time', startTime);
    fd.append('status', status);
    if (variantId) fd.append('route_variant', variantId.toString());
    
    if (gpxFile) {
      fd.append('route_gpx', {
        uri: gpxFile.uri,
        name: gpxFile.name,
        type: 'application/gpx+xml',
      } as any);
    }

    try {
      if (isEdit) {
        await updateEdition(Number(id), fd);
      } else {
        await createEdition(fd);
      }
      router.back();
    } catch (err: any) {
      console.error(err);
      Alert.alert('Error', 'No se pudo guardar la edición.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator color="#8b1a1a" size="large" />
      </View>
    );
  }

  return (
    <ScrollView style={s.container} contentContainerStyle={{ padding: 20 }}>
      <Text style={s.label}>Nombre de la Edición</Text>
      <TextInput
        style={s.input}
        value={name}
        onChangeText={setName}
        placeholder="Ej: Edición XLII"
      />

      <Text style={s.label}>Fecha (AAAA-MM-DD)</Text>
      <TextInput
        style={s.input}
        value={date}
        onChangeText={setDate}
        placeholder="2024-05-20"
      />

      <Text style={s.label}>Hora de salida</Text>
      <TextInput
        style={s.input}
        value={startTime}
        onChangeText={setStartTime}
        placeholder="16:30:00"
      />

      <Text style={s.label}>Estado</Text>
      <View style={s.pickerRow}>
        {(['open', 'closed', 'results_published'] as const).map(opt => (
          <TouchableOpacity
            key={opt}
            style={[s.optBtn, status === opt && s.optBtnActive]}
            onPress={() => setStatus(opt)}
          >
            <Text style={[s.optText, status === opt && s.optTextActive]}>
              {opt === 'open' ? 'Abierta' : opt === 'closed' ? 'Cerrada' : 'Publicada'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={s.label}>Variante de Ruta (Opcional)</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.variantRow}>
        <TouchableOpacity
          style={[s.optBtn, variantId === null && s.optBtnActive]}
          onPress={() => setVariantId(null)}
        >
          <Text style={[s.optText, variantId === null && s.optTextActive]}>Ninguna</Text>
        </TouchableOpacity>
        {variants.map(v => (
          <TouchableOpacity
            key={v.id}
            style={[s.optBtn, variantId === v.id && s.optBtnActive]}
            onPress={() => setVariantId(v.id)}
          >
            <Text style={[s.optText, variantId === v.id && s.optTextActive]}>{v.name}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <Text style={s.label}>Archivo GPX (Sobrescribe variante)</Text>
      <TouchableOpacity style={s.fileBtn} onPress={pickGPX}>
        <Ionicons name="document-text-outline" size={20} color="#1a2744" />
        <Text style={s.fileBtnText}>
          {gpxFile ? gpxFile.name : 'Seleccionar archivo .gpx'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity 
        style={s.saveBtn} 
        onPress={handleSave} 
        disabled={saving}
      >
        {saving ? (
          <ActivityIndicator color="#f5f0e8" />
        ) : (
          <>
            <Ionicons name="save-outline" size={18} color="#f5f0e8" />
            <Text style={s.saveBtnText}>GUARDAR EDICIÓN</Text>
          </>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f5f0e8' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  label: { fontSize: 11, fontWeight: '700', color: '#6b7280', letterSpacing: 1.5, marginTop: 20, marginBottom: 8, textTransform: 'uppercase' },
  input: { backgroundColor: '#fff', padding: 14, fontSize: 15, color: '#1a1a1a', borderWidth: 1, borderColor: '#e5e7eb' },
  pickerRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  optBtn: { paddingVertical: 8, paddingHorizontal: 12, borderWidth: 1, borderColor: '#1a2744', backgroundColor: '#fff' },
  optBtnActive: { backgroundColor: '#1a2744' },
  optText: { fontSize: 12, fontWeight: '600', color: '#1a2744' },
  optTextActive: { color: '#f5f0e8' },
  variantRow: { flexDirection: 'row', gap: 8 },
  fileBtn: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 14, backgroundColor: '#fff', borderStyle: 'dashed', borderWidth: 1, borderColor: '#1a2744' },
  fileBtnText: { fontSize: 13, color: '#1a2744' },
  saveBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: '#8b1a1a', padding: 16, marginTop: 40 },
  saveBtnText: { color: '#f5f0e8', fontSize: 14, fontWeight: '700', letterSpacing: 1 },
});
