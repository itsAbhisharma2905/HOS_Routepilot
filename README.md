# HOS RoutePilot – Full-Stack Route Planning Application

A full-stack route-planning application built with Django REST Framework and React with TypeScript.

## Overview

HOS RoutePilot is a software project focused on route-planning workflows and backend API development. It combines a Django REST Framework backend with a modern React frontend.

The application demonstrates full-stack development, REST API integration, database-backed application logic, and frontend-backend communication.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python, Django, Django REST Framework |
| Frontend | React, TypeScript, Vite |
| Database | Add the actual configured database |
| API | REST |
| Testing | pytest / Django tests, as configured |

## Features

- React-based frontend
- Django REST Framework backend
- API-driven application architecture
- Route-planning workflows
- Frontend and backend integration
- Input validation and error handling
- Automated backend testing

Only retain features that are implemented in the current codebase.

## Architecture

1. Users interact with the React frontend.
2. The frontend communicates with backend REST endpoints.
3. Django REST Framework processes requests.
4. Application logic performs the relevant operations.
5. The backend returns structured responses to the frontend.

## Project Structure

```text
HOS_Routepilot/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   └── ...
├── frontend/
│   ├── src/
│   ├── package.json
│   └── ...
├── README.md
└── .gitignore
```

Adjust this structure to match the actual folders.

## Installation

### Backend

```bash
git clone YOUR_REPOSITORY_URL
cd HOS_Routepilot
```

Create and activate a Python virtual environment:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Install backend dependencies from the backend requirements file:

```bash
pip install -r backend/requirements.txt
```

Run database migrations and start the Django server using the project's configured settings.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Testing

Run the backend tests using the project's configured test command.

If pytest is configured:

```bash
pytest
```

Previously verified development results reported for this project:

- Backend: 55 tests passed
- Frontend TypeScript check: passed
- Production build: passed

Re-run these checks against the current repository before presenting them as current results.

## API Documentation

Add the actual API routes, request examples, response examples, and authentication requirements here.

## Screenshots

Add screenshots of the working application.

## Future Improvements

- CI/CD integration
- API security improvements
- Database optimisation
- Better logging and monitoring
- Deployment documentation
- Additional integration tests

## Project Status

Development / Assessment Project.

This project should not be represented as a certified HOS, ELD, or regulatory-compliance system unless it has undergone the relevant verification.

## Author

Abhi Sharma

GitHub: https://github.com/itsAbhisharma2905
