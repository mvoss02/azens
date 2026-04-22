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
  isEnding = signal(false);
  endError = signal('');

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
    this.endError.set('');
    this.endConfirmOpen.set(true);
  }

  closeEndConfirm(): void {
    if (this.isEnding()) return;
    this.endConfirmOpen.set(false);
  }

  confirmEnd(): void {
    const s = this.live.liveSession();
    if (!s || this.isEnding()) return;
    this.isEnding.set(true);

    this.live.endSession(s.id).subscribe({
      next: () => {
        this.isEnding.set(false);
        this.endConfirmOpen.set(false);
        // Optimistic clear so the banner disappears immediately. Next
        // navigation re-fetches and the server confirms.
        this.live.clearLocal();
      },
      error: (err) => {
        this.isEnding.set(false);
        this.endError.set(err.error?.detail ?? 'Failed to end session.');
      },
    });
  }
}
