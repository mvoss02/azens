import { Component, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { environment } from '../../../environments/environment';

interface Subscription {
  plan: string;
  billing_cycle: string;
  is_active: boolean;
  current_period_end: string | null;
}

interface Plan {
  name: string;
  tier: string;
  priceMonthly: string;
  priceHalfYearly: string;
  priceIdMonthly: string;
  priceIdHalfYearly: string;
  features: string[];
  featured: boolean;
}

@Component({
  selector: 'app-billing',
  standalone: true,
  templateUrl: './billing.component.html',
  styleUrl: './billing.component.css',
})
export class BillingComponent implements OnInit {
  subscription = signal<Subscription | null>(null);
  isLoading = signal(true);
  checkoutLoading = signal('');
  successMessage = signal('');
  halfYearly = signal(false);

  readonly plans: Plan[] = [
    {
      name: 'Analyst',
      tier: 'ANALYST · ENTRY',
      priceMonthly: '€15',
      priceHalfYearly: '€72',
      priceIdMonthly: 'price_analyst_monthly',
      priceIdHalfYearly: 'price_analyst_halfyearly',
      features: ['3 CV screens / month', '3 knowledge drills / month', 'Full feedback reports'],
      featured: false,
    },
    {
      name: 'Associate',
      tier: 'ASSOCIATE · FULL ACCESS',
      priceMonthly: '€35',
      priceHalfYearly: '€168',
      priceIdMonthly: 'price_associate_monthly',
      priceIdHalfYearly: 'price_associate_halfyearly',
      features: ['15 sessions / month', 'Full transcript history', 'Limited case studies (Q2)', 'Priority bot response'],
      featured: true,
    },
    {
      name: 'Managing Director',
      tier: 'MD · EVERYTHING',
      priceMonthly: '€65',
      priceHalfYearly: '€312',
      priceIdMonthly: 'price_md_monthly',
      priceIdHalfYearly: 'price_md_halfyearly',
      features: ['Unlimited sessions', 'All case studies (Q2)', 'Priority processing', 'Full transcript history'],
      featured: false,
    },
  ];

  private readonly api = `${environment.apiUrl}/billing`;

  constructor(private http: HttpClient, private route: ActivatedRoute) {}

  ngOnInit(): void {
    const success = this.route.snapshot.queryParamMap.get('success') === 'true';
    if (success) {
      this.successMessage.set('Payment successful! Your plan is now active.');
      // The Stripe webhook may not have landed yet when the user returns here,
      // so retry the subscription fetch a few times until we see an active sub.
      // Give up after ~5s and just show whatever we've got.
      this.loadSubscriptionWithRetry();
      return;
    }

    this.loadSubscription();
  }

  private loadSubscription(): void {
    this.http.get<Subscription | null>(`${this.api}/subscription`).subscribe({
      next: (sub) => {
        this.subscription.set(sub);
        this.isLoading.set(false);

        // Auto-trigger checkout if plan param is present and user has no subscription
        if (!sub || !sub.is_active) {
          const planSlug = this.route.snapshot.queryParamMap.get('plan');
          if (planSlug) {
            const match = this.plans.find(p => p.name.toLowerCase().replace(' ', '-') === planSlug ||
              p.name.toLowerCase() === planSlug);
            if (match) {
              setTimeout(() => this.subscribe(match), 500);
            }
          }
        }
      },
      error: () => this.isLoading.set(false),
    });
  }

  private loadSubscriptionWithRetry(): void {
    // Poll up to 4 times with a 1.5s gap. If the webhook lands we stop early;
    // if it never does, we settle on whatever the last call returned.
    const maxAttempts = 4;
    const attempt = (n: number) => {
      this.http.get<Subscription | null>(`${this.api}/subscription`).subscribe({
        next: (sub) => {
          this.subscription.set(sub);
          if (sub && sub.is_active) {
            this.isLoading.set(false);
            return;
          }
          if (n < maxAttempts) {
            setTimeout(() => attempt(n + 1), 1500);
          } else {
            this.isLoading.set(false);
          }
        },
        error: () => {
          if (n < maxAttempts) {
            setTimeout(() => attempt(n + 1), 1500);
          } else {
            this.isLoading.set(false);
          }
        },
      });
    };
    attempt(1);
  }

  toggleBilling(): void {
    this.halfYearly.update(v => !v);
  }

  subscribe(plan: Plan): void {
    const priceId = this.halfYearly() ? plan.priceIdHalfYearly : plan.priceIdMonthly;
    this.checkoutLoading.set(plan.name);

    this.http.post<{ checkout_url: string }>(`${this.api}/checkout`, { price_id: priceId }).subscribe({
      next: (res) => { window.location.href = res.checkout_url; },
      error: () => this.checkoutLoading.set(''),
    });
  }

  openPortal(): void {
    this.http.post<{ portal_url: string }>(`${this.api}/portal`, {}).subscribe({
      next: (res) => { window.location.href = res.portal_url; },
    });
  }

  formatDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  }
}
