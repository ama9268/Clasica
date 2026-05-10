import { useEffect, useRef, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import type { TrackingPosition } from '../types';

const WS_BASE =
  process.env.EXPO_PUBLIC_WS_BASE_URL ?? 'ws://10.0.2.2:8000';

export function useTracking(editionId: number) {
  const ws = useRef<WebSocket | null>(null);
  const [positions, setPositions] = useState<Map<number, TrackingPosition>>(
    new Map()
  );
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let active = true;

    (async () => {
      const token = await SecureStore.getItemAsync('access_token');
      const url = `${WS_BASE}/ws/tracking/${editionId}/?token=${token}`;
      ws.current = new WebSocket(url);

      ws.current.onopen = () => active && setConnected(true);
      ws.current.onclose = () => active && setConnected(false);
      ws.current.onerror = () => active && setConnected(false);
      ws.current.onmessage = (e) => {
        if (!active) return;
        try {
          const msg: TrackingPosition = JSON.parse(e.data);
          if (msg.type === 'position_update') {
            setPositions((prev) => new Map(prev).set(msg.user_id, msg));
          }
        } catch {
          // mensaje malformado, ignorar
        }
      };
    })();

    return () => {
      active = false;
      ws.current?.close();
    };
  }, [editionId]);

  function sendPosition(lat: number, lng: number, speed: number) {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ lat, lng, speed }));
    }
  }

  return { positions, connected, sendPosition };
}
