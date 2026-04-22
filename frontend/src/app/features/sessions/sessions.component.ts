import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';
import { ConfirmModalComponent } from '../../shared/components/confirm-modal/confirm-modal.component';
import { LiveSessionService } from '../../core/sessions/live-session.service';

interface Session {
  id: string;
  session_type: string;
  status: string;
  seniority_level: string | null;
  language: string;
  duration_minutes: number;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

@Component({
  selector: 'app-sessions',
  standalone: true,
  imports: [RouterLink, ConfirmModalComponent],
  templateUrl: './sessions.component.html',
  styleUrl: './sessions.component.css',
})
export class SessionsComponent implements OnInit {
  // Exposed to the template to grey out "New session" while a session is
  // already live. Keeps the user from accidentally spinning up a second
  // bot / Daily room (and wasting a quota slot).
  readonly live = inject(LiveSessionService);

  sessions = signal<Session[]>([]);
  isLoading = signal(true);

  // Delete-confirm modal state. Mirrors the CVs-page pattern: stash the
  // pending-target in a single signal where `null` doubles as "modal
  // closed." Two sibling signals guard against double-submit and surface
  // inline errors without blowing away the modal on failure.
  sessionPendingDelete = signal<Session | null>(null);
  isDeleting = signal(false);
  deleteError = signal('');

  private readonly api = `${environment.apiUrl}/session`;

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadSessions();
  }

  // Silent refresh option mirrors the CVs page: used post-delete so the list
  // doesn't flash into a "Loading…" state.
  private loadSessions(opts: { silent?: boolean } = {}): void {
    if (!opts.silent) this.isLoading.set(true);
    this.http.get<Session[]>(`${this.api}/`).subscribe({
      next: (s) => {
        this.sessions.set(s);
        if (!opts.silent) this.isLoading.set(false);
      },
      error: () => {
        if (!opts.silent) this.isLoading.set(false);
      },
    });
  }

  askDelete(session: Session): void {
    this.deleteError.set('');
    this.sessionPendingDelete.set(session);
  }

  cancelDelete(): void {
    // Block dismiss mid-request so the DELETE doesn't land while the user
    // thinks they kept the row.
    if (this.isDeleting()) return;
    this.sessionPendingDelete.set(null);
  }

  confirmDelete(): void {
    const s = this.sessionPendingDelete();
    if (!s || this.isDeleting()) return;
    this.isDeleting.set(true);

    this.http.delete(`${this.api}/${s.id}`).subscribe({
      next: () => {
        this.sessionPendingDelete.set(null);
        this.isDeleting.set(false);
        this.loadSessions({ silent: true });
      },
      error: (err) => {
        // Keep the modal open so the user can see why and retry.
        this.isDeleting.set(false);
        this.deleteError.set(err.error?.detail ?? 'Failed to delete session.');
      },
    });
  }

  typeLabel(type: string): string {
    return { cv_screen: 'CV Screen', knowledge_drill: 'Knowledge Drill', case_study: 'Case Study' }[type] ?? type;
  }

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  formatTime(iso: string | null): string {
    if (!iso) return '';
    return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }

  duration(session: Session): string {
    if (!session.started_at || !session.ended_at) return '—';
    const mins = Math.round((new Date(session.ended_at).getTime() - new Date(session.started_at).getTime()) / 60000);
    return `${mins} min`;
  }
}
