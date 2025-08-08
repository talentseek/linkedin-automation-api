# LinkedIn Automation API Documentation

## Authentication

All API endpoints (except `/auth/login`) require JWT authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### Login
- **POST** `/api/auth/login`
- **Body**: `{"api_key": "linkedin-automation-api-key"}`
- **Response**: JWT token with 24-hour expiration

### Verify Token
- **GET** `/api/auth/verify`
- **Headers**: Authorization: Bearer <token>
- **Response**: Token validity confirmation

### Refresh Token
- **POST** `/api/auth/refresh`
- **Headers**: Authorization: Bearer <token>
- **Response**: New JWT token

## Client Management

### Create Client
- **POST** `/api/clients`
- **Body**: `{"name": "Client Name"}`
- **Response**: Created client object

### Get All Clients
- **GET** `/api/clients`
- **Response**: Array of client objects

### Get Client by ID
- **GET** `/api/clients/<client_id>`
- **Response**: Client object

### Update Client
- **PUT** `/api/clients/<client_id>`
- **Body**: `{"name": "Updated Name"}`
- **Response**: Updated client object

### Delete Client
- **DELETE** `/api/clients/<client_id>`
- **Response**: Success message

## LinkedIn Account Management

### Create LinkedIn Account
- **POST** `/api/clients/<client_id>/linkedin-accounts`
- **Body**: `{"account_id": "unipile_account_id", "status": "pending"}`
- **Response**: Created LinkedIn account object

### Get LinkedIn Accounts for Client
- **GET** `/api/clients/<client_id>/linkedin-accounts`
- **Response**: Array of LinkedIn account objects

### Get LinkedIn Account by ID
- **GET** `/api/linkedin-accounts/<account_id>`
- **Response**: LinkedIn account object

### Update LinkedIn Account
- **PUT** `/api/linkedin-accounts/<account_id>`
- **Body**: `{"status": "connected", "connected_at": "2024-01-01T00:00:00"}`
- **Response**: Updated LinkedIn account object

### Delete LinkedIn Account
- **DELETE** `/api/linkedin-accounts/<account_id>`
- **Response**: Success message

## Data Models

### Client
```json
{
  "id": "uuid",
  "name": "string",
  "created_at": "ISO datetime"
}
```

### LinkedIn Account
```json
{
  "id": "uuid",
  "client_id": "uuid",
  "account_id": "string",
  "status": "pending|connected|disconnected|error",
  "connected_at": "ISO datetime or null"
}
```

## Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error message description"
}
```

Common HTTP status codes:
- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 404: Not Found
- 500: Internal Server Error

