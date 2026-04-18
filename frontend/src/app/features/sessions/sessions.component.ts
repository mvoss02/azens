import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { environment } from '../../../environments/environment';

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
  imports: [RouterLink],
  templateUrl: './sessions.component.html',
  styleUrl: './sessions.component.css',
})
export class SessionsComponent implements OnInit {
  sessions = signal<Session[]>([]);
  isLoading = signal(true);

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<Session[]>(`${environment.apiUrl}/session/`).subscribe({
      next: (s) => { this.sessions.set(s); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
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
