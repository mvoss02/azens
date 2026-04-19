import { Component, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'app-oauth-callback',
  standalone: true,
  template: `
    <div
      style="display:flex;align-items:center;justify-content:center;min-height:100vh;color:var(--color-text-faint);font-size:14px;text-align:center;padding:0 24px"
    >
      {{ message() }}
    </div>
  `,
})
export class OAuthCallbackComponent implements OnInit {
  readonly message = signal('Signing you in...');

  constructor(private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    const fragment = window.location.hash.substring(1);
    const params = new URLSearchParams(fragment);
    const token = params.get('token');

    // No token in the URL = OAuth provider didn't send us back a usable response.
    // Punt to login with a query flag so we can show a friendly error there.
    if (!token) {
      this.router.navigate(['/auth/login'], { queryParams: { error: 'oauth_failed' } });
      return;
    }

    this.auth.handleOAuthCallback(token).subscribe({
      next: (target) => {
        this.router.navigate([target === 'dashboard' ? '/app/dashboard' : '/app/billing']);
      },
      error: () => {
        this.message.set('Sign-in failed. Redirecting...');
        this.router.navigate(['/auth/login'], { queryParams: { error: 'oauth_failed' } });
      },
    });
  }
}
