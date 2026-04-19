import { CommonModule, UpperCasePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, DestroyRef, Input, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';
import { OrbComponent } from '../../shared/components/orb/orb.component';

interface FeedbackReport {
  id: string;
  session_id: string;
  feedback_type: string;
  data: any;
  generated_at: string;
}

interface SessionSnapshot {
  id: string;
  feedback_status: 'pending' | 'generated' | 'failed' | 'skipped';
}

type LoadState =
  | 'loading' // first /session/:id fetch in flight
  | 'pending' // feedback is still being generated — we're polling
  | 'generated' // report fetched, ready to render
  | 'failed' // generator raised; no report will appear without a retry
  | 'skipped' // session had no transcript
  | 'not_found'; // session doesn't exist / isn't ours

// How often to re-hit /session/:id while feedback_status === 'pending'.
// Kept in sync with the 5s cadence agreed in Phase A planning. Polling is
// self-terminating — stops the moment status flips to anything but PENDING.
const POLL_INTERVAL_MS = 5000;

@Component({
  selector: 'app-feedback',
  standalone: true,
  imports: [CommonModule, RouterLink, UpperCasePipe, OrbComponent],
  templateUrl: './feedback.component.html',
  styleUrl: './feedback.component.css',
})
export class FeedbackComponent implements OnInit {
  @Input() id!: string; // session_id from route param

  private readonly http = inject(HttpClient);
  private readonly destroyRef = inject(DestroyRef);

  readonly loadState = signal<LoadState>('loading');
  readonly feedback = signal<FeedbackReport | null>(null);

  private pollTimeoutId: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.destroyRef.onDestroy(() => this.stopPolling());
    this.checkSessionStatus();
  }

  /**
   * Single polling cycle: fetch session state, decide what to do next.
   * Kept recursive (via setTimeout) rather than setInterval so a slow
   * backend response can't cause overlapping requests.
   */
  private checkSessionStatus(): void {
    this.http
      .get<SessionSnapshot>(`${environment.apiUrl}/session/${this.id}`)
      .subscribe({
        next: (s) => this.handleSnapshot(s),
        error: (err) => {
          if (err?.status === 404) {
            this.loadState.set('not_found');
          } else {
            // Transient error (network, 5xx) — keep polling. The loadState
            // stays on whatever it was; the user sees their previous UI,
            // not a flash of error for a brief outage.
            this.scheduleNextPoll();
          }
        },
      });
  }

  private handleSnapshot(s: SessionSnapshot): void {
    switch (s.feedback_status) {
      case 'pending':
        this.loadState.set('pending');
        this.scheduleNextPoll();
        break;
      case 'generated':
        // Report exists — fetch the actual data, stop polling.
        this.fetchReport();
        break;
      case 'failed':
        this.loadState.set('failed');
        break;
      case 'skipped':
        this.loadState.set('skipped');
        break;
    }
  }

  private fetchReport(): void {
    this.http
      .get<FeedbackReport>(`${environment.apiUrl}/feedback/${this.id}`)
      .subscribe({
        next: (fb) => {
          this.feedback.set(fb);
          this.loadState.set('generated');
        },
        error: () => {
          // status says GENERATED but /feedback returned 404? Race between
          // the session-status flip and the feedback row commit. Back off
          // and try once more — if it's still broken, fall through to FAILED.
          setTimeout(() => {
            this.http
              .get<FeedbackReport>(`${environment.apiUrl}/feedback/${this.id}`)
              .subscribe({
                next: (fb) => {
                  this.feedback.set(fb);
                  this.loadState.set('generated');
                },
                error: () => this.loadState.set('failed'),
              });
          }, 1500);
        },
      });
  }

  private scheduleNextPoll(): void {
    this.pollTimeoutId = setTimeout(
      () => this.checkSessionStatus(),
      POLL_INTERVAL_MS,
    );
  }

  private stopPolling(): void {
    if (this.pollTimeoutId !== null) {
      clearTimeout(this.pollTimeoutId);
      this.pollTimeoutId = null;
    }
  }

  // ── Existing helpers for the report rendering ──────────────────────

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
