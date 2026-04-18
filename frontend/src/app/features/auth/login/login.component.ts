import { Component, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router, RouterLink } from '@angular/router';
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
  errorMessage = signal('');

  constructor(
    private fb: FormBuilder,
    private auth: AuthService,
    private router: Router,
    private http: HttpClient,
  ) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', Validators.required],
    });
  }

  onSubmit(): void {
    if (this.form.invalid || this.isLoading()) return;
    this.isLoading.set(true);
    this.errorMessage.set('');

    this.auth.login(this.form.getRawValue()).subscribe({
      next: () => this.router.navigate(['/app/dashboard']),
      error: (err) => {
        this.errorMessage.set(err.error?.detail ?? 'Login failed. Please try again.');
        this.isLoading.set(false);
      },
    });
  }

  loginWithGoogle(): void {
    this.http.get<{ redirect_url: string }>(`${environment.apiUrl}/auth/google`).subscribe({
      next: (res) => window.location.href = res.redirect_url,
    });
  }

  loginWithLinkedIn(): void {
    this.http.get<{ redirect_url: string }>(`${environment.apiUrl}/auth/linkedin`).subscribe({
      next: (res) => window.location.href = res.redirect_url,
    });
  }

  get email() { return this.form.get('email')!; }
  get password() { return this.form.get('password')!; }
}
