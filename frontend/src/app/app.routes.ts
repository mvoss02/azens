import { Routes } from '@angular/router';
import { authGuard, adminGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./features/landing/landing.component').then(m => m.LandingComponent),
  },
  {
    path: 'auth',
    loadChildren: () =>
      import('./features/auth/auth.routes').then(m => m.authRoutes),
  },
  {
    path: 'app',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./shared/components/app-shell/app-shell.component').then(m => m.AppShellComponent),
    children: [
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent),
      },
      {
        path: 'sessions',
        loadComponent: () =>
          import('./features/sessions/sessions.component').then(m => m.SessionsComponent),
      },
      {
        path: 'sessions/new',
        loadComponent: () =>
          import('./features/sessions/session-setup.component').then(m => m.SessionSetupComponent),
      },
      {
        path: 'sessions/:id/room',
        loadComponent: () =>
          import('./features/sessions/session-room.component').then(m => m.SessionRoomComponent),
      },
      {
        path: 'cvs',
        loadComponent: () =>
          import('./features/cvs/cvs.component').then(m => m.CvsComponent),
      },
      {
        path: 'billing',
        loadComponent: () =>
          import('./features/billing/billing.component').then(m => m.BillingComponent),
      },
      {
        path: 'settings',
        loadComponent: () =>
          import('./features/settings/settings.component').then(m => m.SettingsComponent),
      },
      {
        path: 'feedback/:id',
        loadComponent: () =>
          import('./features/feedback/feedback.component').then(m => m.FeedbackComponent),
      },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    ],
  },
  {
    path: 'admin',
    canActivate: [authGuard, adminGuard],
    loadComponent: () =>
      import('./features/admin/admin.component').then(m => m.AdminComponent),
  },
  { path: '**', redirectTo: '' },
];
