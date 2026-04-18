import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app-shell.component.html',
  styleUrl: './app-shell.component.css',
})
export class AppShellComponent {
  readonly navItems = [
    { path: '/app/dashboard', label: 'Dashboard', icon: '⊞' },
    { path: '/app/sessions', label: 'Sessions', icon: '◎' },
    { path: '/app/cvs', label: 'My CVs', icon: '▤' },
    { path: '/app/billing', label: 'Billing', icon: '◈' },
    { path: '/app/settings', label: 'Settings', icon: '⚙' },
  ];

  constructor(public auth: AuthService) {}
}
