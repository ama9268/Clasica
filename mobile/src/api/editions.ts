import client from './client';
import type { Edition, EditionDetail, ActivityUploadResult, GeoJSONLineString, RouteVariant } from '../types';

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
  payload: {
    track_geojson: GeoJSONLineString;
    elapsed_time_seconds: number;
    average_moving_speed: number | null;
  }
): Promise<ActivityUploadResult> {
  const { data } = await client.post<ActivityUploadResult>(
    `/editions/${editionId}/activity/`,
    payload
  );
  return data;
}

export async function createEdition(formData: FormData): Promise<EditionDetail> {
  const { data } = await client.post<EditionDetail>('/editions/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function updateEdition(id: number, formData: FormData): Promise<EditionDetail> {
  const { data } = await client.patch<EditionDetail>(`/editions/${id}/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteEdition(id: number): Promise<void> {
  await client.delete(`/editions/${id}/`);
}

export async function addMedia(editionId: number, formData: FormData): Promise<any> {
  const { data } = await client.post(`/editions/${editionId}/media/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function deleteMedia(mediaId: number): Promise<void> {
  await client.delete(`/media/${mediaId}/`);
}

export async function getRouteVariants(): Promise<RouteVariant[]> {
  const { data } = await client.get<RouteVariant[]>('/route-variants/');
  return data;
}
