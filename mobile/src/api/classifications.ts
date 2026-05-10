import client from './client';
import type { Classification, UserStats } from '../types';

export async function getGeneralClassification(): Promise<Classification[]> {
  const { data } = await client.get<Classification[]>(
    '/classifications/general/'
  );
  return data;
}

export async function getUserStats(userId: number): Promise<UserStats> {
  const { data } = await client.get<UserStats>(`/stats/user/${userId}/`);
  return data;
}
