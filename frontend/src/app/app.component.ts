import { Component, NgZone, ChangeDetectorRef, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { DomSanitizer } from '@angular/platform-browser';
import { marked } from 'marked';

interface Citation {
  title: string;
  url: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent implements OnDestroy {
  query: string = '';
  thoughts: string[] = [];
  finalAnswer: any = '';
  citations: Citation[] = [];
  liveThought: string = '';
  isLoading: boolean = false;

  private eventSource: EventSource | null = null;
  // Dynamically build the backend API URL so that it works both on localhost and
  // when the app is accessed from the local network (e.g. 192.168.x.x) or a
  // remote hostname. This avoids cross-origin issues that can silently break
  // the EventSource stream and prevent real-time updates.
  private readonly apiUrl = `${window.location.protocol}//${window.location.hostname}:8000`;

  constructor(
    private http: HttpClient,
    private zone: NgZone,
    private cdr: ChangeDetectorRef,
    private sanitizer: DomSanitizer
  ) {}

  startSearch() {
    if (!this.query.trim() || this.isLoading) {
      return;
    }

    this.isLoading = true;
    this.thoughts = [];
    this.finalAnswer = '';
    this.citations = [];

    this.http.post<{ run_id: string }>(`${this.apiUrl}/v1/query`, { query: this.query })
      .subscribe({
        next: (res) => {
          this.connectToStream(res.run_id);
        },
        error: (err) => {
          console.error('Failed to start query', err);
          this.isLoading = false;
        }
      });
  }

  private connectToStream(runId: string) {
    if (this.eventSource) {
      this.eventSource.close();
    }

    this.eventSource = new EventSource(`${this.apiUrl}/v1/stream/${runId}`);

    this.eventSource.onmessage = (event) => {
      this.zone.run(() => {
        try {
          const data = JSON.parse(event.data);
          // Debug: log every event coming over the wire
          // eslint-disable-next-line no-console
          console.debug('[SSE]', data);
          this.handleStreamEvent(data);
        } catch (e) {
          console.error('Failed to parse SSE data', event.data, e);
        }
      });
    };

    this.eventSource.onerror = (err) => {
      this.zone.run(() => {
        console.error('EventSource failed', err);
        this.isLoading = false;
        this.eventSource?.close();
      });
    };
  }

  private async handleStreamEvent(data: any) {
    switch (data.type) {
      case 'thought':
        if (this.liveThought) {
          // We were streaming tokens; drop the buffer once full thought arrives
          this.liveThought = '';
        }
        this.thoughts.push(data.text);
        break;
      case 'token':
        // Append streaming token text; if it contains a newline, flush to thoughts list
        const text: string = data.text as string;
        if (text.includes('\n')) {
          const parts = text.split('\n');
          // first part continues current line
          this.liveThought += parts.shift();
          if (this.liveThought.trim()) {
            this.thoughts.push(this.liveThought.trim());
          }
          this.liveThought = '';
          // any subsequent parts (except last if empty) are new thought beginnings
          for (const p of parts) {
            if (p.trim()) {
              this.liveThought = p; // start new buffer
            }
          }
        } else {
          this.liveThought += text;
        }
        break;
      case 'citation':
        this.citations.push(data);
        break;
      case 'final_answer':
        const html = await marked(data.text);
        this.finalAnswer = this.sanitizer.bypassSecurityTrustHtml(html);
        break;
      case 'complete':
        this.isLoading = false;
        this.eventSource?.close();
        this.liveThought = '';
        break;
      case 'error':
        this.finalAnswer = `<p style="color: red;">Error: ${data.message}</p>`;
        this.isLoading = false;
        this.eventSource?.close();
        this.liveThought = '';
        break;
      case 'heartbeat':
        // No UI update needed, but keep the connection alive
        break;
    }
    this.cdr.detectChanges();
  }

  ngOnDestroy() {
    if (this.eventSource) {
      this.eventSource.close();
    }
  }
}
