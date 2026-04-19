import { Component, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../../core/auth/auth.service';
import { VerifyBannerComponent } from '../verify-banner/verify-banner.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, VerifyBannerComponent],
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

  // Drives the mobile drawer (width < 768px). Desktop ignores this — the
  // sidebar is always visible via CSS media query.
  readonly mobileNavOpen = signal(false);

  constructor(public auth: AuthService, private router: Router) {
    // Close the drawer automatically when the user navigates. Without this,
    // clicking "Dashboard" on mobile routes correctly but leaves the drawer
    // open over the new page until manually dismissed.
    this.router.events
      .pipe(
        filter((e) => e instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.mobileNavOpen.set(false));
  }

  toggleMobileNav(): void {
    this.mobileNavOpen.update((v) => !v);
  }

  closeMobileNav(): void {
    this.mobileNavOpen.set(false);
  }
}
