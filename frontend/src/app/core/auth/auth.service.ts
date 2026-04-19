import { HttpClient } from '@angular/common/http';
import { Injectable, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, catchError, filter, map, of, switchMap, take, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { User, TokenResponse, LoginRequest, SignupRequest } from '../models/user.model';

const TOKEN_KEY = 'azens_access_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly api = `${environment.apiUrl}/auth`;
  private _user = signal<User | null>(null);

  // `false` until the initial /me call settles on app boot. Guards wait on
  // this so a hard-refresh on /app/* doesn't redirect to /login before we
  // know who the user is.
  private _bootstrapped$ = new BehaviorSubject<boolean>(false);

  readonly user = this._user.asReadonly();
  readonly isLoggedIn = computed(() => this._user() !== null);
  readonly isAdmin = computed(() => this._user()?.is_admin === true);

  constructor(private http: HttpClient, private router: Router) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      this._bootstrapped$.next(true);
      return;
    }
    this.fetchCurrentUser().subscribe({
      next: () => this._bootstrapped$.next(true),
      error: () => {
        this.clearSession();
        this._bootstrapped$.next(true);
      },
    });
  }

  /**
   * Emits once the initial /me call has settled, then completes.
   * Guards use this to gate their redirect decision on the real auth state.
   */
  whenBootstrapped(): Observable<boolean> {
    return this._bootstrapped$.pipe(
      filter((ready) => ready),
      take(1),
      map(() => this._user() !== null),
    );
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
    // The backend has no /auth/logout endpoint — JWTs are stateless and
    // "logout" is just dropping the token locally. No HTTP call needed.
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

  /**
   * Exchanges the OAuth-returned token for a loaded user profile, then
   * decides where to land the user. Returns the target so the callback
   * component can navigate (keeps routing concerns out of this service).
   */
  handleOAuthCallback(token: string): Observable<'dashboard' | 'billing'> {
    this.saveToken(token);
    return this.fetchCurrentUser().pipe(
      switchMap(() =>
        this.http
          .get<{ is_active?: boolean } | null>(`${environment.apiUrl}/billing/subscription`)
          .pipe(
            // If /billing/subscription itself errors, treat the user as
            // unsubscribed and land them on billing — it's not an auth failure.
            catchError(() => of(null)),
            map((sub) => (sub && sub.is_active ? ('dashboard' as const) : ('billing' as const))),
          ),
      ),
      tap({
        error: () => this.clearSession(),
      }),
    );
  }

  private saveToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
  }

  private clearSession(): void {
    localStorage.removeItem(TOKEN_KEY);
    this._user.set(null);
  }
}
