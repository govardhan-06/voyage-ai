// ==================== User & Auth ====================

export interface User {
  _id: string;
  email: string;
  name: string;
  created_at: string;
  updated_at: string;
  preferences: UserPreferences | null;
  metadata: UserMetadata | null;
}

export interface UserMetadata {
  last_login: string;
  total_trips: number;
}

export interface BudgetRange {
  min: number | null;
  max: number | null;
}

export interface UserPreferences {
  budget_range: BudgetRange;
  travel_style: string[];
  interests: string[];
  preferred_climate: string[];
  preferred_destinations: string[];
  accommodation_type: string[];
  food_preferences: string[];
  activity_preferences: string[];
  risk_tolerance: 'low' | 'moderate' | 'high';
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  name: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
}

// ==================== Trips & Itinerary ====================

export interface TripConstraints {
  destination: string;
  start_date: string;
  end_date: string;
  duration_days: number;
  budget: number;
  travel_group: string;
  traveler_count: number;
  special_constraints: string[];
}

export interface Trip {
  _id: string;
  user_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  trip_constraints: TripConstraints;
  current_version: number;
  final_itinerary_version: number | null;
}

export interface ActivityLocation {
  name: string;
  address: string;
  latitude: number;
  longitude: number;
}

export interface Activity {
  time: string;
  title: string;
  description: string;
  location: ActivityLocation;
  location_name?: string;
  location_address?: string;
  latitude?: number;
  longitude?: number;
  cost_estimate: number;
  tags: string[];
}

export interface ItineraryDay {
  day_number: number;
  date: string;
  activities: Activity[];
}

export interface Itinerary {
  title?: string;
  summary?: string;
  total_cost_estimate: number;
  currency: string;
  days: ItineraryDay[];
}

export interface ItineraryVersion {
  _id: string;
  trip_id: string;
  version_number: number;
  created_at: string;
  created_by: string;
  change_summary: string;
  itinerary: Itinerary;
}

// ==================== Chat ====================

export type ChatStatus = 'clarifying' | 'planning' | 'reviewing' | 'complete';

export interface SlotsCollected {
  destination?: string;
  duration_days?: number;
  travel_group?: string;
  budget_max?: number;
  start_date?: string;
  interests?: string[];
  [key: string]: unknown;
}

export interface TripRequest {
  destination: string;
  duration_days: number;
  budget_max: number;
  travel_group: string;
  traveler_count: number;
  start_date: string;
  interests: string[];
}

export interface ChatResponseData {
  slots_collected?: SlotsCollected;
  itinerary?: Itinerary;
  trip_request?: TripRequest;
  trip_strategy?: {
    destination_overview: string;
    recommended_flights: unknown[];
    recommended_hotels: unknown[];
    daily_themes: string[];
  };
  trip_id?: string;
  itinerary_version_id?: string;
}

export interface ChatResponse {
  status: ChatStatus;
  thread_id: string;
  message: string;
  data: ChatResponseData;
}

export interface ChatRequest {
  user_id: string;
  message: string;
  thread_id: string | null;
}

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  timestamp: string;
  data?: ChatResponseData;
  status?: ChatStatus;
}

export interface ConversationHistory {
  _id: string;
  trip_id: string;
  user_id: string;
  created_at: string;
  messages: ChatMessage[];
}

// ==================== List Responses ====================

export interface TripsListResponse {
  trips: Trip[];
  total: number;
  skip: number;
  limit: number;
}

export interface ItinerariesListResponse {
  itineraries: ItineraryVersion[];
  total: number;
  skip: number;
  limit: number;
}

export interface TripsListParams {
  from_date?: string;
  to_date?: string;
  trip_status?: 'planning' | 'finalized' | 'cancelled';
  skip?: number;
  limit?: number;
}

export interface ItinerariesListParams {
  from_date?: string;
  to_date?: string;
  skip?: number;
  limit?: number;
}
