import client from './client';
import type { GeneralRankingEntry, UserStats } from '../types';

export async function getGeneralClassification(): Promise<GeneralRankingEntry[]> {
  const { data } = await client.get<GeneralRankingEntry[]>(
    '/classifications/general/'
  );
  return data;
}

export async function getUserStats(userId: number): Promise<UserStats> {
  const { data } = await client.get<UserStats>(`/stats/user/${userId}/`);
  return data;
}
