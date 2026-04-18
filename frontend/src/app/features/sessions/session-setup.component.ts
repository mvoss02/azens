import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { AuthService } from '../../core/auth/auth.service';
import { environment } from '../../../environments/environment';

interface CvItem {
  id: string;
  filename: string;
  is_active: boolean;
}

@Component({
  selector: 'app-session-setup',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './session-setup.component.html',
  styleUrl: './session-setup.component.css',
})
export class SessionSetupComponent implements OnInit {
  form: FormGroup;
  cvs = signal<CvItem[]>([]);
  isLoading = signal(false);
  errorMessage = signal('');

  readonly sessionTypes = [
    { value: 'cv_screen', label: 'CV Screening', desc: 'Get drilled on your CV by a senior interviewer' },
    { value: 'knowledge_drill', label: 'Knowledge Drill', desc: 'Test your technical finance knowledge' },
  ];

  readonly seniorityOptions = [
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

  readonly durationOptions = [
    { value: 15, label: '15 min' },
    { value: 30, label: '30 min' },
    { value: 45, label: '45 min' },
    { value: 60, label: '60 min' },
    { value: 90, label: '90 min' },
  ];

  readonly personalityOptions = [
    { value: 'supportive', label: 'Supportive', desc: 'Encouraging, patient, helps you showcase your knowledge' },
    { value: 'balanced', label: 'Balanced', desc: 'Fair and professional: probes but doesn\'t pressure' },
    { value: 'strict', label: 'Strict', desc: 'Demanding and thorough: expects precise answers' },
  ];

  constructor(
    private fb: FormBuilder,
    private http: HttpClient,
    private router: Router,
    private route: ActivatedRoute,
    public auth: AuthService,
  ) {
    const user = this.auth.user();
    this.form = this.fb.group({
      session_type: ['cv_screen', Validators.required],
      cv_id: [null],
      seniority_level: [user?.seniority_level ?? 'analyst'],
      language: [user?.preferred_language ?? 'english'],
      duration_minutes: [30],
      personality: ['balanced'],
    });
  }

  ngOnInit(): void {
    // Check subscription — redirect to billing if not subscribed
    this.http.get<any>(`${environment.apiUrl}/billing/subscription`).subscribe({
      next: (sub) => {
        if (!sub || !sub.is_active) {
          this.router.navigate(['/app/billing']);
        }
      },
      error: () => this.router.navigate(['/app/billing']),
    });

    // Pre-select type from query param if provided
    const type = this.route.snapshot.queryParamMap.get('type');
    if (type && (type === 'cv_screen' || type === 'knowledge_drill')) {
      this.form.patchValue({ session_type: type });
    }

    // Load CVs for CV screen selection
    this.http.get<CvItem[]>(`${environment.apiUrl}/cv/cvs`).subscribe({
      next: (cvs) => {
        this.cvs.set(cvs);
        const active = cvs.find(cv => cv.is_active);
        if (active) {
          this.form.patchValue({ cv_id: active.id });
        }
      },
    });
  }

  get isCvScreen(): boolean {
    return this.form.get('session_type')?.value === 'cv_screen';
  }

  startSession(): void {
    if (this.isLoading()) return;

    const data = this.form.getRawValue();

    if (data.session_type === 'cv_screen' && !data.cv_id) {
      this.errorMessage.set('Please select a CV for the screening session.');
      return;
    }

    if (data.session_type !== 'cv_screen') {
      data.cv_id = null;
    }

    this.isLoading.set(true);
    this.errorMessage.set('');

    this.http.post<any>(`${environment.apiUrl}/session/start`, data).subscribe({
      next: (session) => {
        // TODO: Navigate to the session room with Daily.co credentials
        // For now, navigate to sessions list
        this.router.navigate(['/app/sessions']);
      },
      error: (err) => {
        this.errorMessage.set(err.error?.detail ?? 'Failed to start session. Please try again.');
        this.isLoading.set(false);
      },
    });
  }
}
