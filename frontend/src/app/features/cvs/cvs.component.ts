import { Component, OnInit, signal, ViewChild, ElementRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';

interface CvItem {
  id: string;
  filename: string;
  file_size: number | null;
  is_active: boolean;
  created_at: string;
}

@Component({
  selector: 'app-cvs',
  standalone: true,
  templateUrl: './cvs.component.html',
  styleUrl: './cvs.component.css',
})
export class CvsComponent implements OnInit {
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  cvs = signal<CvItem[]>([]);
  isUploading = signal(false);
  uploadError = signal('');
  isLoading = signal(true);

  private readonly api = `${environment.apiUrl}/cv`;

  constructor(private http: HttpClient, private router: Router) {}

  ngOnInit(): void {
    // Check subscription — redirect to billing if not subscribed
    this.http.get<any>(`${environment.apiUrl}/billing/subscription`).subscribe({
      next: (sub) => {
        if (!sub || !sub.is_active) {
          this.router.navigate(['/app/billing']);
        }
      },
      error: () => this.router.navigate(['/app/billing']),
    });

    this.loadCvs();
  }

  triggerUpload(): void {
    this.fileInput.nativeElement.click();
  }

  async onFileSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    // Client-side pre-checks — cheap local rejections before we hit the server
    // and before S3 silently rejects a mismatched content-type / oversize file.
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      this.uploadError.set('Only PDF files are supported.');
      input.value = '';
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.uploadError.set('File too large. Maximum size is 5 MB.');
      input.value = '';
      return;
    }

    this.isUploading.set(true);
    this.uploadError.set('');

    // 60-second cap on the S3 PUT. On a dead connection fetch() otherwise
    // hangs forever and the spinner never resets.
    const S3_UPLOAD_TIMEOUT_MS = 60_000;

    try {
      const urlRes = await this.http
        .post<{ upload_url: string; s3_key: string }>(`${this.api}/upload-url`, {
          filename: file.name,
          file_size: file.size,
        })
        .toPromise();

      if (!urlRes) throw new Error('Failed to get upload URL');

      const ext = file.name.split('.').pop()?.toLowerCase() ?? 'pdf';

      const abort = new AbortController();
      const timer = setTimeout(() => abort.abort(), S3_UPLOAD_TIMEOUT_MS);
      let s3Response: Response;
      try {
        s3Response = await fetch(urlRes.upload_url, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': `application/${ext}` },
          signal: abort.signal,
        });
      } finally {
        clearTimeout(timer);
      }

      // fetch() resolves even on 4xx/5xx — we have to check ok ourselves or
      // a failed S3 upload silently moves on to /confirm with a missing object.
      if (!s3Response.ok) {
        throw new Error(`Upload to storage failed (${s3Response.status}).`);
      }

      await this.http
        .post(`${this.api}/confirm`, {
          s3_key: urlRes.s3_key,
          filename: file.name,
          file_size: file.size,
        })
        .toPromise();

      this.loadCvs();
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        this.uploadError.set('Upload timed out. Check your connection and try again.');
      } else {
        this.uploadError.set(err?.error?.detail ?? err?.message ?? 'Upload failed. Please try again.');
      }
    } finally {
      this.isUploading.set(false);
      input.value = '';
    }
  }

  activateCv(cv: CvItem): void {
    this.http.put(`${this.api}/${cv.id}/activate`, {}).subscribe({
      next: () => this.loadCvs(),
      error: (err) => {
        this.uploadError.set(err.error?.detail ?? 'Failed to activate CV.');
      },
    });
  }

  deleteCv(cv: CvItem): void {
    if (!confirm(`Delete "${cv.filename}"?`)) return;
    this.http.delete(`${this.api}/${cv.id}`).subscribe({
      next: () => this.loadCvs(),
      error: (err) => {
        this.uploadError.set(err.error?.detail ?? 'Failed to delete CV.');
      },
    });
  }

  private loadCvs(): void {
    this.isLoading.set(true);
    this.http.get<CvItem[]>(`${this.api}/cvs`).subscribe({
      next: (cvs) => { this.cvs.set(cvs); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });
  }

  formatSize(bytes: number | null): string {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  formatDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }
}
