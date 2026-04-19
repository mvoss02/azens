import { Component, OnInit, signal } from '@angular/core';
import { FormBuilder, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.css',
})
export class SettingsComponent implements OnInit {
  form: FormGroup;
  isSaving = signal(false);
  saveMessage = signal('');
  isDeleting = signal(false);

  readonly seniorityOptions = [
    { value: '', label: 'Not set' },
    { value: 'intern', label: 'Intern' },
    { value: 'analyst', label: 'Analyst' },
    { value: 'associate', label: 'Associate' },
    { value: 'vp+', label: 'VP and above' },
  ];

  readonly languageOptions = [
    { value: 'english', label: 'English' },
    { value: 'german', label: 'German' },
    { value: 'spanish', label: 'Spanish' },
    { value: 'italian', label: 'Italian' },
    { value: 'dutch', label: 'Dutch' },
  ];

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    public auth: AuthService,
  ) {
    this.form = this.fb.group({
      full_name: [''],
      seniority_level: [''],
      preferred_language: ['english'],
    });
  }

  ngOnInit(): void {
    const user = this.auth.user();
    if (user) {
      this.form.patchValue({
        full_name: user.full_name ?? '',
        seniority_level: user.seniority_level ?? '',
        preferred_language: user.preferred_language ?? 'english',
      });
    }
  }

  save(): void {
    if (this.isSaving()) return;
    this.isSaving.set(true);
    this.saveMessage.set('');

    const data = this.form.getRawValue();
    if (data.seniority_level === '') data.seniority_level = null;

    this.http.put(`${environment.apiUrl}/auth/me`, data).subscribe({
      next: () => {
        this.saveMessage.set('Settings saved.');
        this.isSaving.set(false);
        // Refresh the cached user so navbar/name updates pick up the new values.
        // If this refresh itself fails, don't surface it as "save failed" —
        // the save already succeeded; we just have slightly stale local state
        // until the next page load.
        this.auth.fetchCurrentUser().subscribe({ error: () => {} });
      },
      error: () => {
        this.saveMessage.set('Failed to save.');
        this.isSaving.set(false);
      },
    });
  }

  deleteAccount(): void {
    const confirmed = confirm(
      'Are you sure you want to delete your account? This will permanently remove all your data — CVs, sessions, transcripts, feedback. This cannot be undone.'
    );
    if (!confirmed) return;

    this.isDeleting.set(true);
    this.http.delete(`${environment.apiUrl}/auth/delete-account`).subscribe({
      next: () => {
        this.auth.logout();
        this.router.navigate(['/']);
      },
      error: () => {
        this.isDeleting.set(false);
        alert('Failed to delete account. Please try again.');
      },
    });
  }
}
