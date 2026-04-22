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

  refresh(opts: { force?: boolean } = {}): void {
    // Bail if we're inside an optimistic-clear suppress window unless the
    // caller explicitly overrides (e.g. an /end POST failed and we need
    // to re-surface the banner so the user can retry, regardless of the
    // window they optimistically set when they clicked).
    if (!opts.force && Date.now() < this.suppressRefreshUntil) return;
    // Clear the suppress window — whichever path made it here, we're
    // doing a real fetch so any lingering window is moot.
    this.suppressRefreshUntil = 0;

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

  // Suppress refreshes for a short window after an optimistic clear. Without
  // this, navigating away from the room right after firing /end causes a
  // race: the navigation-triggered refresh hits `GET /session/` BEFORE the
  // /end POST has committed server-side, reads the still-ACTIVE state, and
  // the banner flashes back on — "you just ended a session, here's a banner
  // saying you have a live one." 3s is long enough to cover the POST's
  // full round-trip + commit in all reasonable conditions.
  private suppressRefreshUntil = 0;

  /** Optimistic UI clear. When called with suppressMs > 0, subsequent
   * refresh() calls are no-ops for that many milliseconds, blocking the
   * race window where a stale /session/ list would re-surface the
   * just-ended row. */
  clearLocal(suppressMs = 0): void {
    this._liveSession.set(null);
    if (suppressMs > 0) {
      this.suppressRefreshUntil = Date.now() + suppressMs;
    }
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
