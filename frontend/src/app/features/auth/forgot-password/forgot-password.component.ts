import { Component, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { AuthLayoutComponent } from '../../../shared/components/auth-layout/auth-layout.component';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, AuthLayoutComponent],
  templateUrl: './forgot-password.component.html',
  styleUrl: './forgot-password.component.css',
})
export class ForgotPasswordComponent {
  form: FormGroup;
  isLoading = signal(false);
  submitted = signal(false);

  constructor(private fb: FormBuilder, private http: HttpClient) {
    this.form = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
    });
  }

  onSubmit(): void {
    if (this.form.invalid || this.isLoading()) return;
    this.isLoading.set(true);

    this.http.post(`${environment.apiUrl}/auth/forgot-password`, this.form.getRawValue()).subscribe({
      next: () => { this.submitted.set(true); this.isLoading.set(false); },
      error: () => { this.submitted.set(true); this.isLoading.set(false); },
    });
  }
}
