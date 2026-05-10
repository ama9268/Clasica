export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  birth_date: string | null;
  club: string;
  photo: string | null;
}

export interface Edition {
  id: number;
  date: string;
  name: string;
  route_distance_km: number | null;
  status: 'open' | 'closed' | 'results_published';
  is_registration_open: boolean;
  results_published: boolean;
}

export interface EditionDetail extends Edition {
  route_geojson: GeoJSONLineString | null;
  classifications: Classification[];
  user_registered: boolean;
}

export interface GeoJSONLineString {
  type: 'LineString';
  coordinates: [number, number][];
}

export interface Classification {
  position_overall: number;
  position_category: number;
  category: string;
  time_seconds: number;
  time_formatted: string;
  user_id: number;
  full_name: string;
  club: string;
}

export interface UserStats {
  id: number;
  full_name: string;
  username: string;
  club: string;
  photo: string | null;
  total_participations: number;
  total_valid: number;
  participations: ParticipationStat[];
}

export interface ParticipationStat {
  edition_id: number;
  edition_name: string;
  edition_date: string;
  is_valid: boolean;
  time_formatted: string;
  position_overall: number | null;
  category: string | null;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface ActivityUploadResult {
  is_valid: boolean;
  validation_score: number;
  elapsed_time_seconds: number;
  elapsed_formatted: string;
}

export interface TrackingPosition {
  type: 'position_update';
  user_id: number;
  username: string;
  lat: number;
  lng: number;
  speed: number;
}
