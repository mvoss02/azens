import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const token = auth.getToken();

  const request = token
    ? req.clone({ headers: req.headers.set('Authorization', `Bearer ${token}`) })
    : req;

  return next(request).pipe(
    catchError((err) => {
      // Auto-logout on 401 only if we actually sent a token. Without this
      // guard, a 401 from /auth/login (wrong password) would also trigger
      // logout, which is wrong — the user never had a session to lose.
      //
      // logout() clears the token + user signal and redirects to `/`.
      // The component that fired the original request still gets the 401
      // in its .subscribe error handler, so any inline UI state resets too.
      if (err instanceof HttpErrorResponse && err.status === 401 && token) {
        auth.logout();
      }
      return throwError(() => err);
    }),
  );
};
