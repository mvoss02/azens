import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { environment } from '../../../environments/environment';

interface Question {
  id: string;
  question: string;
  answer: string;
  topic: string;
  difficulty: string;
  seniority_level: string;
  language: string;
  is_active: boolean;
}

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css',
})
export class AdminComponent implements OnInit {
  questions = signal<Question[]>([]);
  isLoading = signal(true);
  showForm = signal(false);
  editingId = signal<string | null>(null);
  form: FormGroup;

  readonly topics = ['dcf', 'lbo', 'ma', 'accounting', 'valuation', 'general'];
  readonly difficulties = ['easy', 'medium', 'hard'];
  readonly seniorities = ['intern', 'analyst', 'associate', 'vp+'];
  readonly languages = ['english', 'german', 'spanish', 'italian', 'dutch'];

  private readonly api = `${environment.apiUrl}/admin/questions`;

  constructor(private http: HttpClient, private fb: FormBuilder) {
    this.form = this.fb.group({
      question: ['', Validators.required],
      answer: ['', Validators.required],
      topic: ['dcf', Validators.required],
      difficulty: ['easy', Validators.required],
      seniority_level: ['analyst', Validators.required],
      language: ['english'],
    });
  }

  ngOnInit(): void {
    this.loadQuestions();
  }

  loadQuestions(): void {
    this.isLoading.set(true);
    this.http.get<Question[]>(this.api).subscribe({
      next: (q) => { this.questions.set(q); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });
  }

  openCreate(): void {
    this.form.reset({ topic: 'dcf', difficulty: 'easy', seniority_level: 'analyst', language: 'english' });
    this.editingId.set(null);
    this.showForm.set(true);
  }

  openEdit(q: Question): void {
    this.form.patchValue(q);
    this.editingId.set(q.id);
    this.showForm.set(true);
  }

  closeForm(): void {
    this.showForm.set(false);
  }

  save(): void {
    if (this.form.invalid) return;
    const body = this.form.getRawValue();

    if (this.editingId()) {
      this.http.put(`${this.api}/${this.editingId()}`, body).subscribe({
        next: () => { this.closeForm(); this.loadQuestions(); },
      });
    } else {
      this.http.post(this.api, body).subscribe({
        next: () => { this.closeForm(); this.loadQuestions(); },
      });
    }
  }

  deleteQuestion(q: Question): void {
    if (!confirm('Delete this question?')) return;
    this.http.delete(`${this.api}/${q.id}`).subscribe({
      next: () => this.loadQuestions(),
    });
  }
}
