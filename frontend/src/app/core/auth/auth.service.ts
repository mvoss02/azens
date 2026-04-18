import { HttpClient } from '@angular/common/http';
import { Injectable, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { tap, switchMap, Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User, TokenResponse, LoginRequest, SignupRequest } from '../models/user.model';

const TOKEN_KEY = 'azens_access_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = `${environment.apiUrl}/auth`;
  private _user = signal<User | null>(null);

  readonly user = this._user.asReadonly();
  readonly isLoggedIn = computed(() => this._user() !== null);
  readonly isAdmin = computed(() => this._user()?.is_admin === true);

  constructor(private http: HttpClient, private router: Router) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      this.fetchCurrentUser().subscribe({
        error: () => this.clearSession(),
      });
    }
  }

  signup(body: SignupRequest): Observable<User> {
    return this.http.post<TokenResponse>(`${this.api}/signup`, body).pipe(
      tap((res) => this.saveToken(res.access_token)),
      switchMap(() => this.fetchCurrentUser()),
    );
  }

  login(body: LoginRequest): Observable<User> {
    return this.http.post<TokenResponse>(`${this.api}/login`, body).pipe(
      tap((res) => this.saveToken(res.access_token)),
      switchMap(() => this.fetchCurrentUser()),
    );
  }

  logout(): void {
    this.http.post(`${this.api}/logout`, {}).subscribe();
    this.clearSession();
    this.router.navigate(['/']);
  }

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  fetchCurrentUser(): Observable<User> {
    return this.http.get<User>(`${this.api}/me`).pipe(
      tap((user) => this._user.set(user)),
    );
  }

  handleOAuthCallback(token: string): void {
    this.saveToken(token);
    this.fetchCurrentUser().subscribe({
      next: () => this.router.navigate(['/app/dashboard']),
      error: () => this.clearSession(),
    });
  }

  private saveToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  }

  private clearSession(): void {
    localStorage.removeItem(TOKEN_KEY);
    this._user.set(null);
  }
}
