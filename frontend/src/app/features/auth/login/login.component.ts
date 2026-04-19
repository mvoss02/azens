import { Component, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthLayoutComponent } from '../../../shared/components/auth-layout/auth-layout.component';
import { AuthService } from '../../../core/auth/auth.service';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, AuthLayoutComponent],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css',
})
export class LoginComponent {
  form: FormGroup;
  isLoading = signal(false);
  oauthLoading = signal<'google' | 'linkedin' | null>(null);
  errorMessage = signal('');

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private route: ActivatedRoute,
    private http: HttpClient,
  ) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });

    // Surface OAuth errors bounced back from the callback component.
    const oauthError = this.route.snapshot.queryParamMap.get('error');
    if (oauthError === 'oauth_failed') {
      this.errorMessage.set('Sign-in via Google/LinkedIn failed. Please try again.');
    } else if (oauthError === 'email_taken') {
      this.errorMessage.set(
        'An account with this email already exists. Please sign in with your password.',
      );
    }
  }

  onSubmit(): void {
    if (this.form.invalid || this.isLoading()) return;
    this.isLoading.set(true);
    this.errorMessage.set('');

    const raw = this.form.getRawValue();
    const payload = { email: (raw.email ?? '').trim(), password: raw.password };

    this.auth.login(payload).subscribe({
      next: () => this.router.navigate(['/app/dashboard']),
      error: (err) => {
        this.errorMessage.set(err.error?.detail ?? 'Login failed. Please try again.');
        this.isLoading.set(false);
      },
    });
  }

  loginWithGoogle(): void {
    this.startOAuth('google', `${environment.apiUrl}/auth/google`);
  }

  loginWithLinkedIn(): void {
    this.startOAuth('linkedin', `${environment.apiUrl}/auth/linkedin`);
  }

  private startOAuth(provider: 'google' | 'linkedin', endpoint: string): void {
    if (this.oauthLoading()) return;
    this.oauthLoading.set(provider);
    this.errorMessage.set('');
    this.http.get<{ redirect_url: string }>(endpoint).subscribe({
      next: (res) => {
        window.location.href = res.redirect_url;
      },
      error: () => {
        this.errorMessage.set('Could not start the sign-in flow. Please try again.');
        this.oauthLoading.set(null);
      },
    });
  }

  get email() { return this.form.get('email')!; }
  get password() { return this.form.get('password')!; }
}
