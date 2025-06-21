<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# AI Thinking Agent Project

This is a real-time AI thinking agent application with Angular frontend and FastAPI backend.

## Architecture Guidelines

- **Backend**: Use FastAPI with async/await patterns
- **Frontend**: Use Angular 17 standalone components with signals where appropriate
- **Styling**: Use Tailwind CSS with neon-glass theme
- **State Management**: Use RxJS for reactive programming
- **API Communication**: Use Server-Sent Events for real-time streaming

## Code Style

- **Python**: Follow PEP 8, use type hints, async/await for I/O operations
- **TypeScript**: Use strict mode, prefer interfaces over types, use proper typing
- **CSS**: Use Tailwind utility classes, custom CSS only when necessary

## Key Features

- Real-time thought streaming via SSE
- Google search integration with rate limiting
- Selenium web scraping with compliance checks
- OpenAI embeddings and chat completion
- Three-panel responsive UI layout

## Development Patterns

- Services should be properly typed and handle errors gracefully
- Use dependency injection where appropriate
- Implement proper logging throughout the application
- Follow REST API conventions for endpoints
- Use environment variables for configuration
