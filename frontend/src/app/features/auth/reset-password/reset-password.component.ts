import { Component, OnInit, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { AuthLayoutComponent } from '../../../shared/components/auth-layout/auth-layout.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, AuthLayoutComponent],
  template: `
    <app-auth-layout title="Set new password">
      @if (success()) {
        <div class="done">
          <p>Password updated. <a routerLink="/auth/login" class="link">Sign in</a></p>
        </div>
      } @else {
        <form [formGroup]="form" (ngSubmit)="onSubmit()" novalidate>
          <div style="display:flex;flex-direction:column;gap:16px">
            <div style="display:flex;flex-direction:column;gap:6px">
              <label style="font-size:13px;font-weight:500">New password</label>
              <input type="password" class="fi" formControlName="new_password" placeholder="Min. 8 characters" autocomplete="new-password" />
            </div>
            @if (errorMessage()) {
              <div class="err">{{ errorMessage() }}</div>
            }
            <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;padding:12px" [disabled]="isLoading()">
              Update password
            </button>
          </div>
        </form>
      }
    </app-auth-layout>
  `,
  styles: [`
    .fi { width:100%;padding:10px 14px;border:1px solid var(--color-border);border-radius:var(--radius-md);background:var(--color-bg);color:var(--color-text);font-size:14px;outline:none; }
    .fi:focus { border-color:var(--color-amber); }
    .done { text-align:center;padding:20px;border-radius:var(--radius-md);background:rgba(45,122,79,0.06);color:var(--color-success);font-size:14px; }
    .err { font-size:13px;color:var(--color-error);background:rgba(192,57,43,0.06);border:1px solid rgba(192,57,43,0.12);border-radius:var(--radius-md);padding:10px 14px; }
    .link { color:var(--color-amber);font-weight:500; }
  `],
})
export class ResetPasswordComponent implements OnInit {
  form: FormGroup;
  isLoading = signal(false);
  errorMessage = signal('');
  success = signal(false);
  private token = '';

  constructor(private fb: FormBuilder, private route: ActivatedRoute, private http: HttpClient) {
    this.form = this.fb.group({
      new_password: ['', [Validators.required, Validators.minLength(8)]],
    });
  }

  ngOnInit(): void {
    this.token = this.route.snapshot.queryParamMap.get('token') ?? '';
    if (!this.token) this.errorMessage.set('Invalid reset link.');
  }

  onSubmit(): void {
    if (this.form.invalid || this.isLoading() || !this.token) return;
    this.isLoading.set(true);

    this.http.post(`${environment.apiUrl}/auth/reset-password`, {
      token: this.token,
      ...this.form.getRawValue(),
    }).subscribe({
      next: () => { this.success.set(true); this.isLoading.set(false); },
      error: (err) => {
        this.errorMessage.set(err.error?.detail ?? 'Reset failed. The link may have expired.');
        this.isLoading.set(false);
      },
    });
  }
}
