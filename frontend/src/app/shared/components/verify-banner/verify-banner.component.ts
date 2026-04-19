import { HttpClient } from '@angular/common/http';
import { Component, computed, signal } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-verify-banner',
  standalone: true,
  templateUrl: './verify-banner.component.html',
  styleUrl: './verify-banner.component.css',
})
export class VerifyBannerComponent {
  // Visible when the user is loaded AND unverified AND hasn't dismissed it.
  // Dismissal is session-only — we deliberately don't persist it to localStorage,
  // so a fresh tab surfaces the warning again.
  private readonly _dismissed = signal(false);
  readonly isVisible = computed(
    () => this.auth.user() !== null
      && this.auth.user()?.is_verified === false
      && !this._dismissed(),
  );

  readonly isSending = signal(false);
  readonly statusMessage = signal<{ kind: 'success' | 'error'; text: string } | null>(null);

  constructor(private auth: AuthService, private http: HttpClient) {}

  resend(): void {
    if (this.isSending()) return;
    this.isSending.set(true);
    this.statusMessage.set(null);

    this.http.post<{ message: string }>(
      `${environment.apiUrl}/auth/resend-verification`,
      {},
    ).subscribe({
      next: () => {
        this.isSending.set(false);
        this.statusMessage.set({ kind: 'success', text: 'Email sent. Check your inbox.' });
      },
      error: (err) => {
        this.isSending.set(false);
        this.statusMessage.set({
          kind: 'error',
          text: err.error?.detail ?? 'Could not send email. Try again shortly.',
        });
      },
    });
  }

  dismiss(): void {
    this._dismissed.set(true);
  }
}
