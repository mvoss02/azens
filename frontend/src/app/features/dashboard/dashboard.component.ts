import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  recentSessions = signal<any[]>([]);
  hasCv = signal(false);
  subscription = signal<any>(null);
  isLoading = signal(true);

  constructor(public auth: AuthService, private http: HttpClient) {}

  ngOnInit(): void {
    const api = environment.apiUrl;

    this.http.get<any[]>(`${api}/session/`).subscribe({
      next: (s) => { this.recentSessions.set(s.slice(0, 5)); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });

    this.http.get<any>(`${api}/billing/subscription`).subscribe({
      next: (s) => this.subscription.set(s),
      error: () => {},
    });

    this.http.get<any[]>(`${api}/cv/cvs`).subscribe({
      next: (cvs) => this.hasCv.set(cvs.length > 0),
      error: () => {},
    });
  }

  get greeting(): string {
    const name = this.auth.user()?.full_name?.split(' ')[0];
    const hour = new Date().getHours();
    const time = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
    return name ? `${time}, ${name}` : time;
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  sessionTypeLabel(type: string): string {
    return { cv_screen: 'CV Screen', knowledge_drill: 'Knowledge Drill', case_study: 'Case Study' }[type] ?? type;
  }
}
