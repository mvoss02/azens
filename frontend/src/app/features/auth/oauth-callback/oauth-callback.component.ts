import { Component, OnInit } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'app-oauth-callback',
  standalone: true,
  template: `
    <div style="display:flex;align-items:center;justify-content:center;min-height:100vh;color:var(--color-text-faint);font-size:14px">
      Signing you in...
    </div>
  `,
})
export class OAuthCallbackComponent implements OnInit {
  constructor(private auth: AuthService) {}

  ngOnInit(): void {
    const fragment = window.location.hash.substring(1);
    const params = new URLSearchParams(fragment);
    const token = params.get('token');
    if (token) {
      this.auth.handleOAuthCallback(token);
    }
  }
}
