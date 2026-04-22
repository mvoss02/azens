import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { NavigationEnd, Router } from '@angular/router';
import { filter } from 'rxjs';
import { environment } from '../../../environments/environment';

/**
 * Single source of truth for "does the user currently have a live
 * (active or pending-with-started_at) session?"
 *
 * Keeps the active-session banner, the sessions-list "New session" button,
 * the dashboard CTAs, and the session-setup redirect guard all reading the
 * same state, so they can never disagree. The alternative — each page
 * fetching independently — duplicates requests and produces flicker
 * (dashboard says "start a session!" while banner says "you have one
 * running!").
 *
 * Auto-refreshes on every /app/* navigation (one small GET). Callers that
 * know they just changed the state (e.g. after cancelling) can call
 * `clearLocal()` for instant UI feedback without waiting for the refetch.
 */
export interface LiveSession {
  id: string;
  session_type: string;
  status: 'pending' | 'active' | 'completed' | 'error';
  started_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class LiveSessionService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly _liveSession = signal<LiveSession | null>(null);
  readonly liveSession = this._liveSession.asReadonly();

  // Sugar for templates that only care about the boolean. `hasLive()` reads
  // cleaner than `liveSession() !== null` in 4 different @if conditions.
  readonly hasLive = computed(() => this._liveSession() !== null);

  constructor() {
    // Initial fetch plus one per navigation. We skip refresh while the user
    // is IN the room — the whole point is to prompt them to return, pointless
    // when they're already there. Everywhere else under /app/* refreshes.
    this.refresh();
    this.router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe((e) => {
        if (this.isRoomUrl(e.urlAfterRedirects)) {
          this._liveSession.set(null);
          return;
        }
        this.refresh();
      });
  }

  private isRoomUrl(url: string): boolean {
    return url.startsWith('/app/sessions/') && url.endsWith('/room');
  }

  refresh(): void {
    this.http
      .get<LiveSession[]>(`${environment.apiUrl}/session/`)
      .subscribe({
        next: (sessions) => {
          // The list comes back newest-first from the backend, and we only
          // surface the newest live row. An older zombie is rare (the user
          // flow doesn't allow two starts in parallel, we're also adding
          // a client-side block) but if one existed, the latest-wins
          // policy keeps the UI focused on the most relevant session.
          const live = sessions.find(
            (s) =>
              s.status === 'active' ||
              (s.status === 'pending' && s.started_at !== null),
          );
          this._liveSession.set(live ?? null);
        },
        // Silent — a failed refresh just leaves the stale value.
        // Subsequent navigations will retry.
        error: () => {},
      });
  }

  /** Optimistic UI clear after a successful cancel — no wait for refresh. */
  clearLocal(): void {
    this._liveSession.set(null);
  }

  /**
   * POST /session/:id/end?error=false. Same endpoint the in-room Leave
   * button uses — ends the session cleanly, and the backend's 10% rule
   * decides whether feedback is generated or skipped. Returns the HTTP
   * observable so the caller can react to success/error. Local state is
   * cleared by the caller, usually after the server confirms.
   */
  endSession(sessionId: string) {
    return this.http.post(
      `${environment.apiUrl}/session/${sessionId}/end?error=false`,
      {},
    );
  }
}
