# Ticket 11: Self-Hosted Habitica (FUTURE WORK)

**Status:** NOT STARTED - OUT OF SCOPE
**Priority:** FUTURE - Do this later when Habitica is needed

## Objective
Deploy self-hosted Habitica instance with MongoDB, Redis, and HTTPS support for gamified task management.

## Note
This ticket is currently **out of scope** for the initial dashboard implementation. Habitica has been removed from the main deployment to simplify the initial setup.

**Implement this ticket later when you want to add gamified task management.**

## Tasks

### 1. Set up MongoDB for Habitica
Create MongoDB container with authentication and persistence.

### 2. Set up Redis for Habitica
Create Redis container for session storage.

### 3. Deploy Habitica Application
Deploy the main Habitica container connected to MongoDB and Redis.

### 4. Configure HTTPS Access
Set up Nginx reverse proxy with SSL certificates for secure access.

### 5. Create Setup Scripts
Create automated setup scripts for Habitica deployment.

### 6. Configure Environment Variables
Add all required Habitica environment variables to .env.

### 7. Create Documentation
Document Habitica setup, configuration, and usage.

## Dependencies
- Docker and Docker Compose
- MongoDB knowledge
- SSL certificate generation
- Network configuration understanding

## Estimated Time
2-3 hours

## When to Implement
Implement this ticket when you want to add:
- Gamified task management
- Habit tracking with RPG mechanics
- Integration with Home Assistant for fitness automation
- Character progression based on real-world tasks

## References
- Habitica documentation: https://habitica.fandom.com/
- Self-hosting guide: https://habitica.com/static/front
