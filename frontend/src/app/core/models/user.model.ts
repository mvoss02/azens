export interface User {
  id: string;
  email: string;
  full_name: string | null;
  seniority_level: string | null;
  preferred_language: string;
  is_verified: boolean;
  is_admin: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  full_name?: string;
}
