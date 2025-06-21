import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, FormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'AI Thinking Agent';
  isWorking = 'YES!';
  buttonClicked = 0;

  constructor() {}

  ngOnInit() {
    console.log('AI Thinking Agent initialized');
  }

  ngOnDestroy() {
    console.log('Component destroyed');
  }

  testClick() {
    this.buttonClicked++;
    console.log('Button clicked:', this.buttonClicked);
  }
}
