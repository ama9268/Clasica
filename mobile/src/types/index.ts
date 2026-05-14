export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  birth_date: string | null;
  club: string;
  photo: string | null;
  is_staff: boolean;
}

export interface Edition {
  id: number;
  date: string;
  name: string;
  start_time: string;  // "HH:MM:SS"
  route_distance_km: number | null;
  status: 'open' | 'closed' | 'results_published';
  is_registration_open: boolean;
  results_published: boolean;
}

export interface EditionDetail extends Edition {
  route_geojson: GeoJSONLineString | null;
  elevation_profile: { dist: number; alt: number }[] | null;
  is_live: boolean;
  classifications: Classification[];
  user_registered: boolean;
  weather: WeatherForecast | null;
  media: EditionMedia[];
  participants_count: number;
  participants: { user__full_name: string; user__club: string }[];
}

export interface GeneralRankingEntry {
  user__pk: number;
  user__full_name: string;
  user__username: string;
  user__club: string;
  total: number;
  valid: number;
}

export interface EditionMedia {
  id: number;
  edition: number;
  media_type: 'photo' | 'video';
  photo: string | null;
  video_url: string | null;
  caption: string;
  order: number;
  uploaded_at: string;
}

export interface RouteVariant {
  id: number;
  name: string;
  description: string;
  route_distance_km: number;
}

export interface WeatherForecast {
  temperatura: number | null;
  viento_dir: string | null;
  viento_vel: number | null;
  lluvia: number | null;
  estado_cielo: string | null;
  is_multi?: boolean;
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
  average_moving_speed: number | null;
}

export interface RutaPoint {
  lon: number;
  lat: number;
  speed_kmh: number;
  timestamp: number;
}

export interface TrackingPosition {
  type: 'position_update';
  user_id: number;
  username: string;
  lat: number;
  lng: number;
  speed: number;
}
