import { Component, OnInit, signal, Input } from '@angular/core';
import { UpperCasePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';

interface FeedbackReport {
  id: string;
  session_id: string;
  feedback_type: string;
  data: any;
  generated_at: string;
}

@Component({
  selector: 'app-feedback',
  standalone: true,
  imports: [RouterLink, UpperCasePipe],
  templateUrl: './feedback.component.html',
  styleUrl: './feedback.component.css',
})
export class FeedbackComponent implements OnInit {
  @Input() id!: string; // session_id from route param

  feedback = signal<FeedbackReport | null>(null);
  isLoading = signal(true);
  errorMessage = signal('');

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<FeedbackReport>(`${environment.apiUrl}/feedback/${this.id}`).subscribe({
      next: (fb) => { this.feedback.set(fb); this.isLoading.set(false); },
      error: (err) => {
        this.errorMessage.set(err.error?.detail ?? 'Feedback not available yet.');
        this.isLoading.set(false);
      },
    });
  }

  get data(): any {
    return this.feedback()?.data ?? {};
  }

  get categoryScores(): { label: string; value: number }[] {
    const scores = this.data.category_scores;
    if (!scores) return [];
    return Object.entries(scores).map(([key, value]) => ({
      label: key.replace(/_/g, ' '),
      value: value as number,
    }));
  }

  get topicBreakdown(): { topic: string; correct: number; partial: number; wrong: number; total: number }[] {
    const evals = this.data.evaluations;
    if (!evals?.length) return [];

    const byTopic: Record<string, { correct: number; partial: number; wrong: number }> = {};
    for (const ev of evals) {
      if (!byTopic[ev.topic]) byTopic[ev.topic] = { correct: 0, partial: 0, wrong: 0 };
      byTopic[ev.topic][ev.verdict as 'correct' | 'partial' | 'wrong']++;
    }

    return Object.entries(byTopic).map(([topic, counts]) => ({
      topic,
      ...counts,
      total: counts.correct + counts.partial + counts.wrong,
    }));
  }

  topicBarWidth(count: number, total: number): string {
    return total > 0 ? `${(count / total) * 100}%` : '0%';
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  barWidth(score: number): string {
    return `${(score / 10) * 100}%`;
  }

  scoreColor(score: number): string {
    if (score >= 7) return 'var(--color-success)';
    if (score >= 5) return 'var(--color-amber)';
    return 'var(--color-error)';
  }
}
