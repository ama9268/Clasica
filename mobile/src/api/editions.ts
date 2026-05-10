import client from './client';
import type { Edition, EditionDetail, ActivityUploadResult, GeoJSONLineString } from '../types';

export async function getEditions(): Promise<Edition[]> {
  const { data } = await client.get<Edition[]>('/editions/');
  return data;
}

export async function getEdition(id: number): Promise<EditionDetail> {
  const { data } = await client.get<EditionDetail>(`/editions/${id}/`);
  return data;
}

export async function registerEdition(id: number): Promise<void> {
  await client.post(`/editions/${id}/register/`);
}

export async function uploadActivity(
  editionId: number,
  payload: { track_geojson: GeoJSONLineString; elapsed_time_seconds: number }
): Promise<ActivityUploadResult> {
  const { data } = await client.post<ActivityUploadResult>(
    `/editions/${editionId}/activity/`,
    payload
  );
  return data;
}
