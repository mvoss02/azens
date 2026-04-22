import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { ConfirmModalComponent } from '../confirm-modal/confirm-modal.component';
import { LiveSessionService } from '../../../core/sessions/live-session.service';

/**
 * Surfaces a live session that the user hasn't ended. Thin wrapper around
 * LiveSessionService — the service owns the data, this component owns the
 * visual affordance (banner + rejoin/cancel buttons + confirm modal).
 *
 * Daily rooms auto-expire ~10 min after the scheduled end, but the session
 * row stays `active` until explicitly cancelled, counting against the
 * user's monthly quota. This banner is the only reliable recovery path
 * for a row stuck after a crash / closed tab.
 */
@Component({
  selector: 'app-active-session-banner',
  standalone: true,
  imports: [ConfirmModalComponent],
  templateUrl: './active-session-banner.component.html',
  styleUrl: './active-session-banner.component.css',
})
export class ActiveSessionBannerComponent {
  readonly live = inject(LiveSessionService);
  private readonly router = inject(Router);

  // "End" rather than "Cancel": the action ends the session cleanly,
  // which may still produce a feedback report if enough time was spent
  // in the interview (per the backend's 10% threshold rule).
  endConfirmOpen = signal(false);

  typeLabel(type: string | undefined): string {
    if (!type) return 'session';
    const map: Record<string, string> = {
      cv_screen: 'CV screening',
      knowledge_drill: 'knowledge drill',
      case_study: 'case study',
    };
    return map[type] ?? 'session';
  }

  rejoin(): void {
    const s = this.live.liveSession();
    if (!s) return;
    this.router.navigate(['/app/sessions', s.id, 'room']);
  }

  openEndConfirm(): void {
    this.endConfirmOpen.set(true);
  }

  closeEndConfirm(): void {
    this.endConfirmOpen.set(false);
  }

  confirmEnd(): void {
    const s = this.live.liveSession();
    if (!s) return;

    // Fire-and-forget: close the modal + clear the banner immediately so
    // the user isn't stuck staring at an "Ending…" button while the POST
    // finishes. The endpoint itself is fast, but the user explicitly
    // asked for "do this in the background when they click yes."
    //
    // Suppress the service's auto-refresh for 3s so the next /app/*
    // navigation doesn't race our still-in-flight POST and re-surface
    // the banner from stale ACTIVE state. If the POST genuinely fails,
    // the suppress window expires and the next navigation refresh does
    // surface it again — which is what we want.
    this.endConfirmOpen.set(false);
    this.live.clearLocal(3000);

    this.live.endSession(s.id).subscribe({
      error: (err) => {
        console.warn('endSession background POST failed:', err);
        // Force a refresh to re-surface the banner for the user to retry.
        // The `force` flag bypasses the suppress window we set above —
        // the end didn't stick, so the suppression is no longer valid.
        this.live.refresh({ force: true });
      },
    });
  }
}
