import { Injectable, NgZone } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';

export interface QueryResponse {
  run_id: string;
}

@Injectable({
  providedIn: 'root'
})
export class AgentService {
  private readonly apiUrl = environment.apiUrl || 'http://localhost:8000';

  constructor(private http: HttpClient, private ngZone: NgZone) {}

  createQuery(query: string, model?: string): Observable<QueryResponse> {
    const payload: any = { query };
    if (model) {
      payload.model = model;
    }
    console.log('🔌 Making request to:', `${this.apiUrl}/v1/query`);
    console.log('🔌 Payload:', payload);
    
    return this.http.post<QueryResponse>(`${this.apiUrl}/v1/query`, payload).pipe(
      tap(response => console.log('✅ Response received:', response)),
      catchError(error => {
        console.error('❌ HTTP Error:', error);
        return throwError(() => new Error('Failed to create query'));
      })
    );
  }

  getEventStream(runId: string): Observable<any> {
    return new Observable(observer => {
      const eventSource = new EventSource(`${this.apiUrl}/v1/stream/${runId}`);
      
      eventSource.onmessage = (event) => {
        this.ngZone.run(() => {
          try {
            const data = JSON.parse(event.data);
            console.log('🔥 EventSource received:', data.type);
            observer.next(data);
            
            if (data.type === 'complete' || data.type === 'error') {
              eventSource.close();
              observer.complete();
            }
          } catch (error) {
            console.error('🚨 EventSource parse error:', error, 'Raw data:', event.data);
            observer.error(error);
            eventSource.close();
          }
        });
      };

      eventSource.onerror = (error) => {
        this.ngZone.run(() => {
          console.error('🚨 EventSource connection error:', error);
          observer.error(error);
          eventSource.close();
        });
      };

      // Cleanup when the observable is unsubscribed
      return () => {
        if (eventSource.readyState !== EventSource.CLOSED) {
          console.log('🔌 Closing EventSource connection.');
          eventSource.close();
        }
      };
    });
  }
}
