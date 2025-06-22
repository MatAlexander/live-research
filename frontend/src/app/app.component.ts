import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AgentService } from './services/agent.service';
import { Subscription } from 'rxjs';
import { switchMap, tap } from 'rxjs/operators';
import { environment } from '../environments/environment';

// FILE LOGGING UTILITY
class FileLogger {
  private logs: string[] = [];
  
  log(message: string) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${message}`;
    this.logs.push(logEntry);
    console.log(logEntry);
    
    // Also send to backend for file logging
    fetch('http://localhost:8000/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: logEntry })
    }).catch(() => {}); // Ignore errors
  }
  
  downloadLogs() {
    const blob = new Blob([this.logs.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'frontend-debug.log';
    a.click();
  }
}

const logger = new FileLogger();

interface ThoughtEvent {
  type: string;
  content: string;
  timestamp: number;
  favicon?: string;
  bubbleType?: string;
  bubbleIcon?: string;
  bubbleText?: string;
}

interface Citation {
  title: string;
  url: string;
  snippet: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'AI Thinking Agent';
  
  // Simple properties
  query = 'What are the latest developments in quantum computing and how might they impact cybersecurity?';
  selectedModel = 'o4-mini';
  isLoading = false;
  thoughts: ThoughtEvent[] = [];
  finalAnswer = '';
  citations: Citation[] = [];
  
  // Available models
  availableModels = [
    { value: 'o4-mini', label: 'o4-mini' },
    { value: 'o3-mini', label: 'o3-mini' }
  ];
  
  private querySubscription?: Subscription;

  constructor(private agentService: AgentService, private cdr: ChangeDetectorRef) {}

  ngOnInit() {
    logger.log('🚀 Component initialized');
    this.testBackendConnection();
  }

  private async testBackendConnection() {
    try {
      logger.log('🔌 Testing backend connection...');
      const response = await fetch(`${environment.apiUrl}/health`);
      const data = await response.json();
      logger.log(`✅ Backend connection successful: ${data.status}`);
    } catch (error) {
      logger.log(`❌ Backend connection failed: ${error}`);
    }
  }

  async testConnection() {
    try {
      logger.log('🧪 Manual connection test started');
      const response = await fetch(`${environment.apiUrl}/health`);
      const data = await response.json();
      logger.log(`✅ Manual test successful: ${JSON.stringify(data)}`);
      alert('✅ Backend connection successful!');
    } catch (error) {
      logger.log(`❌ Manual test failed: ${error}`);
      alert('❌ Backend connection failed! Check console for details.');
    }
  }

  downloadLogs() {
    logger.downloadLogs();
  }

  testSimpleStream() {
    const testRunId = 'test-' + Date.now();
    logger.log(`🧪 Testing simple stream with run_id: ${testRunId}`);
    
    // Clear current state
    this.thoughts = [];
    this.finalAnswer = '';
    this.isLoading = true;
    
    // Test the simple stream endpoint directly
    const eventSource = new EventSource(`http://localhost:8000/test-stream/${testRunId}`);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        logger.log(`🧪 Test stream received: ${data.type} - ${data.text}`);
        this.handleStreamEvent(data);
        this.cdr.detectChanges();
        
        if (data.type === 'complete') {
          eventSource.close();
          this.isLoading = false;
          this.cdr.detectChanges();
        }
      } catch (error) {
        logger.log(`🧪 Test stream parse error: ${error}`);
      }
    };
    
    eventSource.onerror = (error) => {
      logger.log(`🧪 Test stream error: ${error}`);
      eventSource.close();
      this.isLoading = false;
      this.cdr.detectChanges();
    };
  }

  ngOnDestroy() {
    this.querySubscription?.unsubscribe();
  }

  clearHistory() {
    this.thoughts = [];
    this.finalAnswer = '';
    this.citations = [];
  }

  // TEST METHOD - Add fake thoughts to debug UI updates
  addTestThought() {
    const testThought: ThoughtEvent = {
      type: 'thought',
      content: `Test thought ${Date.now()}`,
      timestamp: Date.now()
    };
    logger.log(`🧪 BEFORE adding test thought - Array length: ${this.thoughts.length}`);
    logger.log(`🧪 Adding test thought: ${testThought.content}`);
    
    this.thoughts = [...this.thoughts, testThought];
    
    logger.log(`🧪 AFTER adding test thought - Array length: ${this.thoughts.length}`);
    logger.log(`🧪 Full thoughts array: ${JSON.stringify(this.thoughts.map(t => t.content))}`);
    
    this.cdr.detectChanges();
    logger.log(`🧪 Change detection triggered manually`);
  }

  public requestStartTime: number | null = null;
  public finalAnswerTime: number | null = null;
  public thoughtElapsedSeconds: number = 0;

  submitQuery() {
    const queryText = this.query;
    if (!queryText.trim() || this.isLoading) return;

    logger.log(`🚀 Starting query: "${queryText}"`);
    logger.log(`🚀 Model: ${this.selectedModel}`);

    this.isLoading = true;
    this.thoughts = [];
    this.finalAnswer = '';
    this.citations = [];
    this.cdr.detectChanges(); // Immediately reflect cleared state

    // Unsubscribe from any previous stream before starting a new one
    this.querySubscription?.unsubscribe();

    this.collapseThinkingPanel = false; // Expand panel on new query

    this.requestStartTime = Date.now();
    this.finalAnswerTime = null;
    this.thoughtElapsedSeconds = 0;

    this.querySubscription = this.agentService.createQuery(queryText, this.selectedModel).pipe(
      tap(response => {
        logger.log(`✅ Query created with run_id: ${response.run_id}`);
      }),
      switchMap(response => {
        if (!response || !response.run_id) {
          throw new Error('Invalid run_id received');
        }
        logger.log('🔌 Connecting to event stream...');
        return this.agentService.getEventStream(response.run_id);
      })
    ).subscribe({
      next: (event) => {
        logger.log(`📡 Component received event: ${event.type}`);
        this.handleStreamEvent(event);
        // The service runs this in the zone, but an extra detectChanges can help ensure timely updates
        this.cdr.detectChanges();
      },
      error: (error) => {
        logger.log(`❌ Stream pipeline error: ${error.message || JSON.stringify(error)}`);
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      complete: () => {
        logger.log('✅ Stream pipeline complete.');
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  public collapseThinkingPanel = false;
  public showThoughtsCollapsed = false;
  public thoughtCollapseSeconds = 0;
  public thoughtCollapseTimer: any = null;

  // Call this to collapse the panel and start the timer
  collapsePanelWithTimer() {
    this.collapseThinkingPanel = true;
    this.showThoughtsCollapsed = true;
    this.thoughtCollapseSeconds = 0;
    if (this.thoughtCollapseTimer) {
      clearInterval(this.thoughtCollapseTimer);
    }
    this.thoughtCollapseTimer = setInterval(() => {
      this.thoughtCollapseSeconds++;
      this.cdr.detectChanges();
    }, 1000);
  }

  // Call this to expand the panel again
  expandThinkingPanel() {
    this.collapseThinkingPanel = false;
    this.showThoughtsCollapsed = false;
    if (this.thoughtCollapseTimer) {
      clearInterval(this.thoughtCollapseTimer);
      this.thoughtCollapseTimer = null;
    }
    this.cdr.detectChanges();
  }

  private handleStreamEvent(event: any) {
    logger.log(`🔄 handleStreamEvent called with: ${event.type}`);
    logger.log(`🔄 Event data: ${JSON.stringify(event)}`);
    logger.log(`🔄 BEFORE processing - thoughts.length: ${this.thoughts.length}, finalAnswer.length: ${this.finalAnswer.length}`);
    // Skip embedding tool events
    if ((event.type === 'tool_use' || event.type === 'tool_result') && event.tool === 'embedding') {
      return;
    }
    // Skip web_scraper tool_result events for successful scrape
    if (event.type === 'tool_result' && event.tool === 'web_scraper' && event.result && event.result.startsWith('Successfully scraped content')) {
      return;
    }
    switch (event.type) {
      case 'thought':
      case 'tool_use':
      case 'tool_result':
        logger.log(`💭 Processing thought event: ${event.type}`);
        logger.log(`💭 Content: ${event.text || event.content}`);
        const newThought = this.createThoughtEvent(event);
        if (event.favicon) newThought.favicon = event.favicon;
        logger.log(`💭 Created thought object: ${JSON.stringify(newThought)}`);
        const oldLength = this.thoughts.length;
        this.thoughts = [...this.thoughts, newThought];
        const newLength = this.thoughts.length;
        logger.log(`💭 Array update: ${oldLength} -> ${newLength}`);
        logger.log(`💭 Updated thoughts array: ${JSON.stringify(this.thoughts.map(t => t.content.substring(0, 50)))}`);
        break;
        
      case 'final_answer':
      case 'complete':
        logger.log(`💡 Processing final answer: ${event.text || event.content}`);
        logger.log(`💡 Final answer length: ${(event.text || event.content || '').length} chars`);
        const finalContent = event.text || event.content;
        this.finalAnswer = this.finalAnswer ? this.finalAnswer + ' ' + finalContent : finalContent;
        logger.log(`💡 Final answer updated: ${this.finalAnswer.length} chars`);
        this.finalAnswerTime = Date.now();
        if (this.requestStartTime) {
          this.thoughtElapsedSeconds = Math.round((this.finalAnswerTime - this.requestStartTime) / 1000);
        }
        // Collapse the thinking panel after a short delay
        setTimeout(() => {
          this.collapsePanelWithTimer();
          this.cdr.detectChanges();
        }, 1200);
        break;
        
      case 'citation':
        logger.log(`📚 Processing citation: ${event.title}`);
        this.citations = [...this.citations, {
          title: event.title || 'Unknown Source',
          url: event.url || '',
          snippet: event.snippet || ''
        }];
        logger.log(`📚 Citations updated: ${this.citations.length} total`);
        break;
        
      case 'citations':
        logger.log(`📚 Processing citations array: ${event.citations?.length || 0} items`);
        this.citations = event.citations || [];
        break;
        
      default:
        logger.log(`❓ Unknown event type: ${event.type}`);
    }
    
    logger.log(`🔄 AFTER processing - thoughts.length: ${this.thoughts.length}`);
  }

  private createThoughtEvent(event: any): ThoughtEvent {
    let content = '';
    let bubbleType = '';
    let bubbleIcon = '';
    let bubbleText = '';
    switch (event.type) {
      case 'thought':
        content = event.text || event.content;
        break;
      case 'tool_use':
        if (event.tool === 'google_search' && event.details) {
          // Extract search keyword from details
          const match = event.details.match(/Query: '(.+)'/);
          bubbleType = 'search';
          bubbleIcon = 'search';
          bubbleText = match ? match[1] : event.details;
          content = '';
        } else if (event.tool === 'web_scraper' && event.details) {
          // Extract domain from details
          const match = event.details.match(/URL: (https?:\/\/)?([^\/]+)/);
          bubbleType = 'scrape';
          bubbleIcon = event.favicon || '';
          bubbleText = match ? match[2] : event.details;
          content = '';
        } else {
          content = `${event.action || 'Tool Use'}: ${event.details || ''}`;
        }
        break;
      case 'tool_result':
        content = `✅ ${event.result || 'Tool completed'}`;
        break;
    }
    const thought: ThoughtEvent = {
      type: event.type,
      content: content,
      timestamp: Date.now(),
      favicon: event.favicon,
      bubbleType: bubbleType,
      bubbleIcon: bubbleIcon,
      bubbleText: bubbleText
    };
    return thought;
  }

  trackByIndex(index: number, item: ThoughtEvent): number {
    return item.timestamp;
  }

  trackByCitation(index: number, item: Citation): string {
    return item.url || index.toString();
  }

  getToolDisplayName(tool?: string): string {
    if (!tool) return 'Tool';
    return tool.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  }
}