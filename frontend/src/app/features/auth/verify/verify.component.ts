import { Component, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AuthLayoutComponent } from '../../../shared/components/auth-layout/auth-layout.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-verify',
  standalone: true,
  imports: [RouterLink, AuthLayoutComponent],
  template: `
    <app-auth-layout title="Email verification">
      @switch (status()) {
        @case ('loading') {
          <p style="color:var(--color-text-faint);font-size:14px">Verifying your email...</p>
        }
        @case ('success') {
          <div style="padding:20px;border-radius:var(--radius-md);background:rgba(45,122,79,0.06);color:var(--color-success);text-align:center;font-size:14px">
            <p>Your email has been verified.</p>
            <a routerLink="/app/dashboard" class="btn btn-primary" style="width:100%;justify-content:center;margin-top:16px">Go to dashboard</a>
          </div>
        }
        @case ('error') {
          <div style="padding:20px;border-radius:var(--radius-md);background:rgba(192,57,43,0.06);color:var(--color-error);text-align:center;font-size:14px">
            <p>This verification link is invalid or has expired.</p>
            <a routerLink="/auth/login" class="btn btn-ghost" style="width:100%;justify-content:center;margin-top:16px">Back to sign in</a>
          </div>
        }
      }
    </app-auth-layout>
  `,
})
export class VerifyComponent implements OnInit {
  status = signal<'loading' | 'success' | 'error'>('loading');

  constructor(private route: ActivatedRoute, private http: HttpClient) {}

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.status.set('error');
      return;
    }

    this.http.get(`${environment.apiUrl}/auth/verify?token=${token}`).subscribe({
      next: () => this.status.set('success'),
      error: () => this.status.set('error'),
    });
  }
}
