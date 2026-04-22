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
    // If the POST somehow fails, the next /session/ refresh (fires on
    // every /app/* navigation) re-surfaces the banner and the user can
    // try again. We also eagerly refresh on error to surface that faster
    // without waiting for the next navigation.
    this.endConfirmOpen.set(false);
    this.live.clearLocal();

    this.live.endSession(s.id).subscribe({
      error: (err) => {
        console.warn('endSession background POST failed:', err);
        this.live.refresh();
      },
    });
  }
}
