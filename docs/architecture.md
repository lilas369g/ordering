# Architecture Summary

## Style
The backend is a **modular monolith**:
- one deployable backend service
- one primary PostgreSQL database
- clear module boundaries
- future extraction path if a module becomes large enough

## Backend modules
- users
- customers
- employees
- roles_permissions
- otp
- catalog
- inventory
- cart
- orders
- notifications
- common

## Auth strategy
### Customer auth
- phone-based registration/login
- OTP verification
- customer-facing JWT tokens

### Employee auth
- dashboard login
- staff role assignment
- permission-based access control
- separate API namespace and stricter policies

## Catalog strategy
- Product
- ProductOption
- OptionValue
- ProductVariant
- VariantOptionValue

## Inventory strategy
Inventory is stored at the **variant level**. This prevents overselling for combinations such as size/color/weight.

## Order strategy
- immutable order item price snapshot
- explicit status transitions
- inventory reservation and stock movements
- API versioning from day one
