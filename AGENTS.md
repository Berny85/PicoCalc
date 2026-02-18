# PicoCalc - Agent Documentation

> **Language Note**: This project uses German as its primary language for code comments, documentation, and UI text.

## Project Overview

**PicoCalc** is a web-based product price calculator designed for small manufacturing businesses. It calculates production costs for various product types including 3D printing, sticker production, die-cut stickers, and laser engraving.

- **Repository**: https://github.com/Berny85/PicoCalc.git
- **Production URL**: http://192.168.50.8:5000
- **Primary Language**: German (code, comments, documentation, UI)

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11 + FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 |
| Frontend | Jinja2 Templates + HTMX |
| Styling | Vanilla CSS (in templates) |
| Deployment | Docker + Docker Compose |
| Infrastructure | Intel NUC with Unraid OS |
| CI/CD | GitHub Actions |

## Project Structure

```
PicoCalc/
├── app/                          # Main application code
│   ├── main.py                   # FastAPI app with all routes
│   ├── models.py                 # SQLAlchemy database models
│   ├── database.py               # Database configuration
│   ├── requirements.txt          # Python dependencies
│   ├── Dockerfile                # Application container image
│   └── templates/                # Jinja2 HTML templates
│       ├── base.html             # Base layout with navigation
│       ├── index.html            # Dashboard
│       ├── materials/            # Material management UI
│       ├── machines/             # Machine management UI
│       ├── products/             # Product forms and details
│       └── partials/             # HTMX partial templates
├── .github/workflows/            # CI/CD configuration
│   └── deploy.yml                # GitHub Actions workflow
├── backup/                       # Database backup scripts
│   ├── backup-script.sh          # Automated backup script
│   └── restore-script.sh         # Database restore script
├── docker-compose.yaml           # Development configuration
├── docker-compose.prod.yml       # Production configuration
├── postgresql.conf               # PostgreSQL WAL configuration
├── deploy.sh                     # NUC deployment script (Bash)
├── deploy-to-nuc.ps1             # Windows deployment script
├── backup-to-local.ps1           # Local backup download script
├── quick-deploy.sh               # Fast deployment (no rebuild)
├── README.md                     # Project overview (German)
└── DEPLOYMENT.md                 # Detailed deployment docs (German)
```

## Architecture

### Development Environment (Windows 11)
- **Docker Desktop** for containerization
- **Local URL**: http://localhost:5000
- **Database**: PostgreSQL on port 5432
- **pgAdmin**: http://localhost:5050

### Production Environment (Intel NUC with Unraid)
- **IP**: 192.168.50.8
- **PicoCalc App**: http://192.168.50.8:5000
- **Portainer**: http://192.168.50.8:9000 (Docker management)
- **Dozzle**: http://192.168.50.8:8080 (Log viewer)
- **pgAdmin**: http://192.168.50.8:5050

## Database Models

### Machine (`models.py`)
Represents production equipment (3D printers, cutters, etc.):
- `name`, `machine_type` (3d_printer, cutter_plotter, other)
- `depreciation_euro` - Device depreciation cost
- `lifespan_hours` - Expected lifetime
- `power_kw` - Power consumption
- Methods: `calculate_cost_per_hour()`, `calculate_cost_per_unit()`

### Material (`models.py`)
Represents raw materials (filaments, sticker sheets, paper):
- `name`, `material_type` (filament, sticker_sheet, paper, other)
- `brand`, `color`, `unit` (kg, sheet, piece)
- `price_per_unit`

### Product (`models.py`)
Central entity with type-specific fields:
- **Common**: `name`, `product_type`, `category`, `labor_hours`, `labor_rate_per_hour`
- **3D Print**: `filament_material_id`, `filament_weight_g`, `print_time_hours`
- **Sticker/Paper**: `sheet_material_id`, `sheet_count`, `units_per_sheet`
- **Laser**: `laser_material`, `laser_design_name`, `laser1_*`, `laser2_*`, `laser3_*`
- Method: `calculate_costs()` - Returns cost breakdown and selling price suggestions

## Product Types & Categories

### Product Types (internal)
- `3d_print` - 3D printed objects
- `sticker_sheet` - Sticker sheets
- `diecut_sticker` - Die-cut stickers
- `laser_engraving` - Laser engraved items

### Categories (user-facing)
Dekoration, Technik, Ersatzteile, Spielzeug, Werkzeuge, Sticker, Papierprodukte, Sonstiges

## Development Workflow

### Local Development
```powershell
# Start development environment
docker-compose up -d

# Access application at http://localhost:5000
# Access pgAdmin at http://localhost:5050
```

### Making Changes
1. Edit code in `app/` directory
2. Changes auto-reload in development (uvicorn --reload)
3. Test locally
4. Commit and push to main branch

### Deployment
```powershell
# Windows: Automated deployment via PowerShell
.\deploy-to-nuc.ps1

# Or manual deployment via SSH:
ssh root@192.168.50.8
cd /mnt/user/appdata/picocalc
git pull origin main
docker compose -f docker-compose.prod.yml up --build -d
```

## Build and Test Commands

### Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down

# Rebuild after dependency changes
docker-compose up --build -d
```

### Production (on NUC)
```bash
# Full deployment with rebuild
docker compose -f docker-compose.prod.yml up --build -d

# Quick restart (no rebuild)
docker compose -f docker-compose.prod.yml up -d

# View container status
docker compose -f docker-compose.prod.yml ps

# View logs
docker logs picocalc-app
docker logs picocalc-db
```

## Key Configuration Files

### Environment Variables
Production requires these environment variables (set in Portainer):
- `DB_PASSWORD` - PostgreSQL password
- `SECRET_KEY` - FastAPI secret key

### Database Connection
Development: `postgresql://printuser:printpass@db:5432/printcalc`
Production: `postgresql://printuser:${DB_PASSWORD}@db:5432/printcalc`

### PostgreSQL Configuration
- `postgresql.conf` - WAL archiving configuration for point-in-time recovery
- Backups run 3x daily (06:00, 12:00, 18:00)
- 14-day retention policy

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/deploy.yml`):
1. Triggers on push to `main` branch
2. Builds Docker image from `app/` directory
3. Pushes to Docker Hub (`bernys/picocalc:latest`)
4. Triggers Portainer webhook for auto-deployment

Required GitHub Secrets:
- `DOCKER_USERNAME` - Docker Hub username
- `DOCKER_PASSWORD` - Docker Hub access token
- `PORTAINER_WEBHOOK_URL` - Portainer stack webhook URL

## Backup and Restore

### Automated Backups
- Runs 3x daily via `docker-volume-backup` container
- Location: `/mnt/user/backups/picocalc/`
- Format: `backup-YYYY-MM-DDTHH-MM-SS.tar.gz`
- Retention: 14 days

### Manual Backup to Local Machine
```powershell
.\backup-to-local.ps1
```

### Restore from Backup (on NUC)
```bash
# Restore latest backup
./backup/restore-script.sh latest

# Restore specific backup
./backup/restore-script.sh 20250115_120000
```

## Code Style Guidelines

### Python
- Use type hints where practical
- Follow PEP 8 naming conventions
- Database models use German field names for business concepts
- Route handlers use German variable names for form data

### Template Naming
- List views: `{resource}/list.html`
- Form views: `{resource}/form.html` or `form_{type}.html`
- Detail views: `{resource}/detail.html`
- HTMX partials: `partials/{name}.html`

### Database Conventions
- Table names: plural, lowercase (machines, materials, products)
- Primary keys: `id` (Integer, auto-increment)
- Timestamps: `created_at`, `updated_at`
- Foreign keys: `{resource}_id`

## Security Considerations

1. **No sensitive data in code** - Passwords via environment variables
2. **Database** - PostgreSQL behind Docker network, port 5432 exposed only on host
3. **Secrets management** - Docker secrets or Portainer environment variables
4. **Backups** - Automated backups with retention
5. **No authentication** - Current version has no user authentication (internal use only)

## Common Tasks

### Adding a New Product Type
1. Add type to `PRODUCT_TYPES` in `main.py`
2. Add type-specific fields to `Product` model in `models.py`
3. Create form template: `templates/products/form_{type}.html`
4. Add routes for create/edit in `main.py`
5. Add calculation logic to `calculate_costs()` in models

### Adding Database Fields
1. Add column to model in `models.py`
2. Update form templates
3. Update route handlers in `main.py`
4. Since there's no migration system currently, manual DB update or rebuild required

### Updating Dependencies
1. Edit `app/requirements.txt`
2. Rebuild containers: `docker-compose up --build -d`
3. Test thoroughly
4. Commit changes

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is ready
docker exec picocalc-db pg_isready -U printuser

# View database logs
docker logs picocalc-db
```

### Application Won't Start
```bash
# Check for syntax errors
docker logs picocalc-app

# Verify environment variables
docker exec picocalc-app env | grep DATABASE
```

### Reset Development Database
```bash
docker-compose down -v  # Removes volumes
docker-compose up -d    # Recreates fresh
```

## Important Notes for AI Agents

1. **German Language**: All user-facing text is German. Maintain German for new UI text, comments, and documentation.

2. **No ORM Migrations**: The project uses `Base.metadata.create_all()` on startup. Schema changes require:
   - Model updates
   - Manual DB migration or recreation

3. **Cost Calculation Logic**: The core business logic is in `models.py`:
   - `Machine.calculate_cost_per_hour()` - Includes depreciation + electricity
   - `Product.calculate_costs()` - Aggregates all cost components
   - Selling prices calculated with 30%, 50%, 100% margins

4. **Static Electricity Price**: `STROM_PREIS_KWH = 0.22` (€/kWh) is hardcoded in models.py

5. **Template Inheritance**: All templates extend `base.html` which includes HTMX and common styling

6. **Development vs Production**:
   - Dev: Code mounted as volume, auto-reload enabled
   - Prod: Code baked into image, no volume mounts for app code
