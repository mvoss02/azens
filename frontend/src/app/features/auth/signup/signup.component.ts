import { Component, signal } from '@angular/core';
import { AbstractControl, FormBuilder, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthLayoutComponent } from '../../../shared/components/auth-layout/auth-layout.component';
import { AuthService } from '../../../core/auth/auth.service';
import { I18nService } from '../../../core/i18n/i18n.service';
import { environment } from '../../../../environments/environment';

function passwordsMatch(control: AbstractControl): ValidationErrors | null {
  const password = control.get('password')?.value;
  const confirm = control.get('confirmPassword')?.value;
  return password && confirm && password !== confirm ? { passwordMismatch: true } : null;
}

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, AuthLayoutComponent],
  templateUrl: './signup.component.html',
  styleUrl: './signup.component.css',
})
export class SignupComponent {
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
    private i18n: I18nService,
  ) {
    this.form = this.fb.group(
      {
        full_name: ['', Validators.required],
        email: ['', [Validators.required, Validators.email]],
        // Backend enforces min_length=10 on SignUp.password — mirror it here
        // so the user gets a local error instead of a 422 round-trip.
        password: ['', [Validators.required, Validators.minLength(10)]],
        confirmPassword: ['', Validators.required],
      },
      { validators: passwordsMatch },
    );

    const oauthError = this.route.snapshot.queryParamMap.get('error');
    if (oauthError === 'oauth_failed') {
      this.errorMessage.set('Sign-up via Google/LinkedIn failed. Please try again.');
    } else if (oauthError === 'email_taken') {
      this.errorMessage.set(
        'An account with this email already exists. Please log in instead.',
      );
    }
  }

  onSubmit(): void {
    if (this.form.invalid || this.isLoading()) return;
    this.isLoading.set(true);
    this.errorMessage.set('');

    const raw = this.form.getRawValue();
    const { confirmPassword, ...rest } = raw;
    const payload = {
      ...rest,
      email: (rest.email ?? '').trim(),
      full_name: (rest.full_name ?? '').trim(),
    };

    this.auth.signup(payload).subscribe({
      next: () => {
        // Set preferred language from the landing page selection
        this.http.put(`${environment.apiUrl}/auth/me`, {
          preferred_language: this.i18n.backendValue(),
        }).subscribe({
          error: () => {
            // Non-fatal: the user is signed up, just couldn't persist language.
            // They can change it later in Settings. Don't block navigation.
          },
        });

        // Always go to billing after signup — nudge them to pick a plan
        const plan = this.route.snapshot.queryParamMap.get('plan');
        this.router.navigate(['/app/billing'], plan ? { queryParams: { plan } } : {});
      },
      error: (err) => {
        this.errorMessage.set(err.error?.detail ?? 'Signup failed. Please try again.');
        this.isLoading.set(false);
      },
    });
  }

  signupWithGoogle(): void {
    this.startOAuth('google', `${environment.apiUrl}/auth/google`);
  }

  signupWithLinkedIn(): void {
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
        this.errorMessage.set('Could not start the sign-up flow. Please try again.');
        this.oauthLoading.set(null);
      },
    });
  }

  get fullName() { return this.form.get('full_name')!; }
  get email() { return this.form.get('email')!; }
  get password() { return this.form.get('password')!; }
  get confirmPassword() { return this.form.get('confirmPassword')!; }
  get passwordMismatch() { return this.form.hasError('passwordMismatch') && this.confirmPassword.touched; }
}
