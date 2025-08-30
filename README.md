# Restaurant POS Backend

A Django REST API backend for restaurant point-of-sale management.

## Features

- Location management (add/remove branches)
- Menu item management
- Order processing
- Authentication system

## Setup

1. Clone repository:
   ```bash
   git clone https://github.com/imvijay0/point_of_sale_project.git
   cd point_of_sale_project
   ```

2. Build and run with Docker Compose:
   ```bash
   docker-compose build
   docker-compose up
   ```

That's it! The application will:
- Set up all required directories
- Run migrations in the correct order
- Start the development server

The API will be available at http://localhost:8000/

## Manual Setup (if needed)

If you encounter any issues during the automatic setup:

### For Linux/macOS:
```bash
chmod +x setup.sh
./setup.sh
docker-compose build
docker-compose up
```

### For Windows:
```cmd
setup.bat
docker-compose build
docker-compose up
```

## Troubleshooting

If you encounter any migration issues:

1. Stop all containers:
   ```bash
   docker-compose down
   ```

2. Remove the volume:
   ```bash
   docker volume rm point_of_sale_project_postgres_data
   ```

3. Rebuild and restart:
   ```bash
   docker-compose build
   docker-compose up
   ```
   cd point_of_sale_project
   ```

2. Build and run with Docker Compose:
   ```bash
   docker-compose build
   docker-compose up
   ```

That's it! The application will:
- Set up all required directories
- Run migrations in the correct order
- Start the development server

The API will be available at http://localhost:8000/

## Manual Setup (if needed)

If you encounter any issues during the automatic setup:

### For Linux/macOS:
```bash
chmod +x setup.sh
./setup.sh
docker-compose build
docker-compose up
```

### For Windows:
```cmd
setup.bat
docker-compose build
docker-compose up
```

## Troubleshooting

If you encounter any migration issues:

1. Stop all containers:
   ```bash
   docker-compose down
   ```

2. Remove the volume:
   ```bash
   docker volume rm point_of_sale_project_postgres_data
   ```

3. Rebuild and restart:
   ```bash
   docker-compose build
   docker-compose up


   docker compose exec web bash
   ```