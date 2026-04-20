import { Component, OnInit, computed, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AuthLayoutComponent } from '../../shared/components/auth-layout/auth-layout.component';
import { environment } from '../../../environments/environment';
import { I18nService } from '../../core/i18n/i18n.service';

// idle   → page loaded with a token, waiting for the user to click Confirm.
//          This is the explicit-consent step — we do NOT fire the DELETE on
//          page load. Reasons:
//            1) Gmail/Outlook/corp security scanners prefetch links. We use
//               DELETE-over-XHR (not GET) anyway, but belt-and-suspenders.
//            2) Accidental clicks on mobile happen. Extra confirm = one
//               saved unsubscribe.
// pending → user clicked Confirm; DELETE in flight.
// success → DELETE returned 204.
// error   → DELETE failed, or no token was in the URL at all.
type Status = 'idle' | 'pending' | 'success' | 'error';

@Component({
  selector: 'app-unsubscribe',
  standalone: true,
  imports: [RouterLink, AuthLayoutComponent],
  templateUrl: './unsubscribe.component.html',
  styleUrl: './unsubscribe.component.css',
})
export class UnsubscribeComponent implements OnInit {
  status = signal<Status>('idle');
  private token: string | null = null;

  readonly pageTitle = computed(() => {
    switch (this.status()) {
      case 'idle':
        return this.i18n.t('unsubscribe.idle.title');
      case 'pending':
        return this.i18n.t('unsubscribe.title');
      case 'success':
        return this.i18n.t('unsubscribe.success.title');
      case 'error':
        return this.i18n.t('unsubscribe.error.title');
    }
  });

  constructor(
    private route: ActivatedRoute,
    private http: HttpClient,
    public i18n: I18nService,
  ) {}

  ngOnInit(): void {
    this.token = this.route.snapshot.paramMap.get('token');
    // No token in the URL → jump straight to error. There's nothing to
    // confirm; showing an "Unsubscribe?" button with no target would be
    // confusing.
    if (!this.token) {
      this.status.set('error');
    }
  }

  confirm(): void {
    // Guard: don't double-fire if the user double-clicks, and don't let
    // them click Confirm once we've already succeeded/errored.
    if (this.status() !== 'idle' || !this.token) return;

    this.status.set('pending');

    // DELETE (not GET) so the request is semantically mutative and never
    // triggered by link prefetchers / scanners. Route is public — the
    // token itself is the authorization.
    this.http
      .delete(`${environment.apiUrl}/waitlist/unsubscribe/${this.token}`)
      .subscribe({
        next: () => this.status.set('success'),
        error: () => this.status.set('error'),
      });
  }
}
