# E-Commerce Platform Monorepo

Production-oriented starter monorepo for a customer mobile app, admin dashboard, and Django backend.

## What is included
- Django + DRF backend scaffold
- Modular monolith app layout
- PostgreSQL-ready settings
- JWT-ready REST API structure
- Customer auth separated from employee auth in domain/application design
- React admin dashboard starter
- Flutter mobile app starter
- Architecture docs

## Monorepo structure
```text
backend/      Django API
admin-web/    React admin dashboard starter
mobile-app/   Flutter mobile app starter
docs/         Architecture and roadmap
```

## Functional alignment with the SRS
This scaffold is designed around the uploaded SRS, including:
- customer mobile app and admin web panel
- OTP flows
- products with variants and selectable attributes
- cart, checkout, orders, reorder
- inventory tracking
- employee roles and permissions
- delivery and reporting hooks

## Notes
This is a **scaffolded foundation**, not a fully finished commercial product. It gives you the correct architecture, models, modules, and starter endpoints so implementation can continue cleanly.

## Backend quick start
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Admin web quick start
```bash
cd admin-web
npm install
npm run dev
```

## Mobile app quick start
```bash
cd mobile-app
flutter pub get
flutter run
```
