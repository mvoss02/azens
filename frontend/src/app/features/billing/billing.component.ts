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

type PlanSlug = 'analyst' | 'associate' | 'managing_director';
type CycleSlug = 'monthly' | 'halfyearly';

interface Plan {
  name: string;
  tier: string;
  // Slug sent to the backend. The backend resolves (slug, cycle) to the real
  // Stripe price ID — keep Stripe identifiers server-side where they belong.
  slug: PlanSlug;
  priceMonthly: string;
  priceHalfYearly: string;
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
      slug: 'analyst',
      priceMonthly: '€15',
      priceHalfYearly: '€72',
      features: ['3 CV screens / month', '3 knowledge drills / month', 'Full feedback reports'],
      featured: false,
    },
    {
      name: 'Associate',
      tier: 'ASSOCIATE · FULL ACCESS',
      slug: 'associate',
      priceMonthly: '€35',
      priceHalfYearly: '€168',
      features: ['15 sessions / month', 'Full transcript history', 'Limited case studies (Q2)', 'Priority bot response'],
      featured: true,
    },
    {
      name: 'Managing Director',
      tier: 'MD · EVERYTHING',
      slug: 'managing_director',
      priceMonthly: '€65',
      priceHalfYearly: '€312',
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

        // Auto-trigger checkout if plan param is present and user has no subscription.
        // Match directly against plan.slug — no whitespace / dash gymnastics.
        if (!sub || !sub.is_active) {
          const planSlug = this.route.snapshot.queryParamMap.get('plan') as PlanSlug | null;
          if (planSlug) {
            const match = this.plans.find(p => p.slug === planSlug);
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
    const cycle: CycleSlug = this.halfYearly() ? 'halfyearly' : 'monthly';
    this.checkoutLoading.set(plan.name);

    this.http
      .post<{ checkout_url: string }>(`${this.api}/checkout`, {
        plan: plan.slug,
        cycle,
      })
      .subscribe({
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

  // Backend sends the enum value as a snake_case slug (e.g. 'managing_director').
  // Render it as a human-friendly title — works for any future plans too as
  // long as the enum values stay slug-shaped.
  planLabel(plan: string | null): string {
    if (!plan) return '—';
    return plan
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  }

  cycleLabel(cycle: string | null): string {
    if (cycle === 'monthly') return 'Monthly';
    if (cycle === 'halfyearly') return 'Every 6 months';
    return cycle ?? '—';
  }
}
