import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.whenBootstrapped().pipe(
    map((loggedIn) => {
      if (loggedIn) return true;
      router.navigate(['/auth/login']);
      return false;
    }),
  );
};

export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.whenBootstrapped().pipe(
    map(() => {
      if (auth.isAdmin()) return true;
      router.navigate(['/app/dashboard']);
      return false;
    }),
  );
};
