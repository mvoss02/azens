import { Component, OnInit, signal, ViewChild, ElementRef } from '@angular/core';
import { HttpClient } from '@angular/common/http';
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

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadCvs();
  }

  triggerUpload(): void {
    this.fileInput.nativeElement.click();
  }

  async onFileSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.isUploading.set(true);
    this.uploadError.set('');

    try {
      const urlRes = await this.http
        .post<{ upload_url: string; s3_key: string }>(`${this.api}/upload-url`, {
          filename: file.name,
          file_size: file.size,
        })
        .toPromise();

      if (!urlRes) throw new Error('Failed to get upload URL');

      const ext = file.name.split('.').pop()?.toLowerCase() ?? 'pdf';
      await fetch(urlRes.upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': `application/${ext}` },
      });

      await this.http
        .post(`${this.api}/confirm`, {
          s3_key: urlRes.s3_key,
          filename: file.name,
          file_size: file.size,
        })
        .toPromise();

      this.loadCvs();
    } catch (err: any) {
      this.uploadError.set(err?.error?.detail ?? 'Upload failed. Please try again.');
    } finally {
      this.isUploading.set(false);
      input.value = '';
    }
  }

  activateCv(cv: CvItem): void {
    this.http.put(`${this.api}/${cv.id}/activate`, {}).subscribe({
      next: () => this.loadCvs(),
    });
  }

  deleteCv(cv: CvItem): void {
    if (!confirm(`Delete "${cv.filename}"?`)) return;
    this.http.delete(`${this.api}/${cv.id}`).subscribe({
      next: () => this.loadCvs(),
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
