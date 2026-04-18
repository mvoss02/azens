import { Component, signal } from '@angular/core';
import { AbstractControl, FormBuilder, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
import { AuthLayoutComponent } from '../../../shared/components/auth-layout/auth-layout.component';
import { AuthService } from '../../../core/auth/auth.service';
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
  errorMessage = signal('');

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private http: HttpClient,
  ) {
    this.form = this.fb.group(
      {
        full_name: ['', Validators.required],
        email: ['', [Validators.required, Validators.email]],
        password: ['', [Validators.required, Validators.minLength(8)]],
        confirmPassword: ['', Validators.required],
      },
      { validators: passwordsMatch },
    );
  }

  onSubmit(): void {
    if (this.form.invalid || this.isLoading()) return;
    this.isLoading.set(true);
    this.errorMessage.set('');

    const { confirmPassword, ...payload } = this.form.getRawValue();
    this.auth.signup(payload).subscribe({
      next: () => this.router.navigate(['/app/dashboard']),
      error: (err) => {
        this.errorMessage.set(err.error?.detail ?? 'Signup failed. Please try again.');
        this.isLoading.set(false);
      },
    });
  }

  signupWithGoogle(): void {
    this.http.get<{ redirect_url: string }>(`${environment.apiUrl}/auth/google`).subscribe({
      next: (res) => window.location.href = res.redirect_url,
    });
  }

  signupWithLinkedIn(): void {
    this.http.get<{ redirect_url: string }>(`${environment.apiUrl}/auth/linkedin`).subscribe({
      next: (res) => window.location.href = res.redirect_url,
    });
  }

  get fullName() { return this.form.get('full_name')!; }
  get email() { return this.form.get('email')!; }
  get password() { return this.form.get('password')!; }
  get confirmPassword() { return this.form.get('confirmPassword')!; }
  get passwordMismatch() { return this.form.hasError('passwordMismatch') && this.confirmPassword.touched; }
}
